import socket
import time
from contextlib import closing as closing_context

from .library import libstore
from .log import LoggerFactory
from .threadmgr import threader
from .gossip import gossiper
from .kv import kvmgr
from .topic import topiker, TOPIC_CONFIGURATION_AUTOMATION
from .jsonmgr import jsoner
from .util import exec_command, get_uuid, unicode_to_bytes, b64_into_unicode, b64_into_bytes, string_to_b64unicode
from .udprouter import udprouter
from .encrypter import get_encrypter

# Global logger for this part
logger = LoggerFactory.create_logger('executer')


class EXECUTER_PACKAGE_TYPES(object):
    CHALLENGE_ASK = 'executor::challenge-ask'
    CHALLENGE_RETURN = 'executor::challenge-return'
    CHALLENGE_PROPOSAL = 'executor::challenge-proposal'
    EXECUTION_DONE = 'executor::execution-done'


class Executer(object):
    def __init__(self):
        # Execs launch as threads
        self.execs = {}
        # Challenge send so we can match the response when we will get them
        self.challenges = {}
        # Set myself as master of the executor:: udp messages
        udprouter.declare_handler('executor', self)
    
    
    def manage_message(self, message_type, message, source_addr):
        # Someone is asking us a challenge, ok do it
        if message_type == EXECUTER_PACKAGE_TYPES.CHALLENGE_ASK:
            self.manage_exec_challenge_ask_message(message, source_addr)
        
        elif message_type == EXECUTER_PACKAGE_TYPES.CHALLENGE_RETURN:
            self.manage_exec_challenge_return_message(message, source_addr)
        
        else:
            logger.error('Someone did send us unknown UDP message: %s' % message_type)
    
    
    def manage_exec_challenge_ask_message(self, m, addr):
        public_key = get_encrypter().get_mf_pub_key()
        # If we don't have the public key, bailing out now
        if public_key is None:
            logger.error('EXEC skipping exec call because we do not have a public key')
            return
        requester_uuid = m['from']
        requester_node = gossiper.get(requester_uuid, None)
        if requester_node is None:
            logger.error('A node is asking us to execute a command, but we do not known about it: %s(%s)' % (requester_uuid, addr))
            return
        logger.info('Did receive a challenge ask from requester: %s' % requester_node['name'])
        # get the with execution id from ask
        exec_id = m.get('exec_id', None)
        if exec_id is None:
            return
        cid = get_uuid()  # challgenge id
        challenge = get_uuid()
        e = {'ctime': int(time.time()), 'challenge': None, 'exec_id': exec_id}
        self.challenges[cid] = e
        # return a tuple with only the first element useful (str)
        encrypter = libstore.get_encrypter()
        # As the encrypter to generate a challenge based on the zone public key that the asker
        # will have to prove to solve thanks to the private key (that I do not have)
        challenge_string, encrypted_challenge = encrypter.generate_challenge(gossiper.zone)  # TODO: check if we must send from our ouw zone or not
        e['challenge'] = challenge_string
        logger.info('EXEC asking us a challenge, return %s(%s) to %s' % (challenge, encrypted_challenge, addr))
        
        challenge_payload = {'type'     : EXECUTER_PACKAGE_TYPES.CHALLENGE_PROPOSAL,
                             'fr'       : gossiper.uuid,
                             'challenge': encrypted_challenge,
                             'cid'      : cid
                             }
        # NOTE: cannot talk to classic gossip port as the requestor is waiting in a specific port
        gossiper.send_message_to_other(requester_uuid, challenge_payload, force_addr=addr)
    
    
    def manage_exec_challenge_return_message(self, m, addr):
        public_key = get_encrypter().get_mf_pub_key()
        # Don't even look at it if we do not have a public key....
        if public_key is None:
            return
        cid = m.get('cid', '')
        response64 = m.get('response', '')
        cmd = m.get('cmd', '')
        _from = m.get('fr', '')
        # skip invalid packets
        if not cid or not response64 or not cmd:
            return
        # Maybe we got a bad or old challenge response...
        p = self.challenges.get(cid, None)
        if not p:
            return
        # We will have to save result in KV store
        exec_id = p['exec_id']
        try:
            response = b64_into_unicode(response64)
        except ValueError as exp:
            logger.error('EXEC invalid base64 response from %s: %s' % (addr, exp))
            return
        
        logger.info('EXEC got a challenge return from %s for %s:%s' % (_from, cid, response))
        
        if response != p['challenge']:
            logger.error('The received challenge (%s) is different than the store one (%s)' % (response, p['challenge']))
            return
        
        # now try to decrypt the response of the other
        # This function take a tuple of size=2, but only look at the first...
        logger.info('EXEC GOT GOOD FROM A CHALLENGE, DECRYPTED DATA', cid, response, p['challenge'], response == p['challenge'])
        threader.create_and_launch(self._do_launch_exec, name='do-launch-exec-%s' % exec_id, args=(cid, exec_id, cmd, addr), part='executer', essential=True)
    
    
    # Someone ask us to launch a new command (was already auth by RSA keys)
    def _do_launch_exec(self, cid, exec_id, cmd, addr):
        logger.info('EXEC launching a command %s' % cmd)
        try:
            rc, output, err = exec_command(cmd)
        except Exception as exp:
            rc = 2
            output = ''
            err = 'The command (%s) did raise an error: %s' % (cmd, exp)
        logger.info("EXEC RETURN for command %s : %s %s %s" % (cmd, rc, output, err))
        o = {'output': output, 'rc': rc, 'err': err, 'cmd': cmd}
        j = jsoner.dumps(o)
        # Save the return and put it in the KV space
        key = '__exec/%s' % exec_id
        kvmgr.put_key(key, unicode_to_bytes(j), ttl=3600)  # only one hour live is good :)
        
        # Now send a finish to the asker
        with closing_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:
            payload = {'type'   : EXECUTER_PACKAGE_TYPES.EXECUTION_DONE,
                       'exec_id': exec_id,
                       'cid'    : cid}
            packet = jsoner.dumps(payload)
            encrypter = libstore.get_encrypter()
            enc_packet = encrypter.encrypt(packet)
            logger.info('EXEC: sending a exec done packet to %s:%s' % addr)
            logger.info('EXEC: sending a exec done for the execution %s and the challenge id %s' % (exec_id, cid))
            try:
                sock.sendto(enc_packet, addr)
            except Exception:
                logger.error('Cannot return execution done to the node at %s' % str(addr))
    
    
    # Launch an exec thread and save its uuid so we can keep a look at it then
    def launch_exec(self, cmd, group):
        uid = get_uuid()
        logger.info('EXEC ask for launching command', cmd)
        all_uuids = []
        
        for (uuid, n) in gossiper.nodes.items():
            if (group == '*' or group in n['groups']) and n['state'] == 'alive':
                exec_id = get_uuid()  # to get back execution id
                all_uuids.append((uuid, exec_id))
        
        execution_ctx = {'cmd'   : cmd,
                         'group' : group,
                         'thread': None,
                         'res'   : {},
                         'nodes' : all_uuids,
                         'ctime' : int(time.time())}
        self.execs[uid] = execution_ctx
        threader.create_and_launch(self._do_exec_thread, name='exec-%s' % uid, args=(execution_ctx,), essential=True, part='executer')
        return uid
    
    
    # Look at all nodes, ask them a challenge to manage with our priv key (they all got
    # our pub key)
    def _do_exec_thread(self, execution_ctx):
        # first look at which command we need to run
        cmd = execution_ctx['cmd']
        logger.info('EXEC ask for launching command', cmd)
        all_uuids = execution_ctx['nodes']
        logger.info('WILL EXEC command for %s' % all_uuids)
        for (nuid, exec_id) in all_uuids:
            remote_execution = self._launch_execution_to_other_node(nuid, cmd, exec_id)
            if remote_execution is not None:
                execution_ctx['res'][nuid] = remote_execution
    
    
    def _get_error_execution(self, execution_result, err):
        logger.error(err)
        execution_result['state'] = 'error'
        execution_result['output'] = err
        execution_result['err'] = err
        return execution_result
    
    
    def _launch_execution_to_other_node(self, node_uuid, command, execution_id):
        node = gossiper.get(node_uuid)
        logger.info('WILL EXEC A NODE? %s' % node)
        if node is None:  # was removed, don't play lotery today...
            return None
        # Get a socket to talk with this node
        with closing_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:  # auto close for this sock
            execution_result = {'node': node, 'challenge': '', 'state': 'pending', 'rc': 3, 'output': '', 'err': '', 'cmd': command}
            logger.info('EXEC asking for node %s' % node['name'])
            
            payload = {'type'   : EXECUTER_PACKAGE_TYPES.CHALLENGE_ASK,
                       'from'   : gossiper.uuid,
                       'exec_id': execution_id}
            packet = jsoner.dumps(payload)
            encrypter = libstore.get_encrypter()
            enc_packet = encrypter.encrypt(packet)
            logger.info('EXEC: sending a challenge request to %s' % node['name'])
            sock.sendto(enc_packet, (node['addr'], node['port']))
            # Now wait for a return
            sock.settimeout(5)
            try:
                raw = sock.recv(1024)
            except socket.timeout as exp:
                err = 'EXEC challenge ask timeout from node %s : %s' % (node['name'], exp)
                return self._get_error_execution(execution_result, err)
            msg = encrypter.decrypt(raw)
            if msg is None:
                err = 'EXEC bad return from node %s' % node['name']
                return execution_result
            try:
                ret = jsoner.loads(msg)
            except ValueError as exp:
                err = 'EXEC bad return from node %s : %s' % (node['name'], exp)
                execution_result['state'] = 'error'
                return execution_result
            
            # TODO: check message type as return
            cid = ret.get('cid', '')  # challenge id
            challenge64 = ret.get('challenge', '')
            if not challenge64 or not cid:
                err = 'EXEC bad return from node %s : no challenge or challenge id' % node['name']
                execution_result['state'] = 'error'
                return execution_result
            
            try:
                challenge = b64_into_bytes(challenge64)  # NOTE: need raw bytes as challenge is binary
            except ValueError:
                err = 'EXEC bad return from node %s : invalid base64' % node['name']
                execution_result['state'] = 'error'
                return execution_result
            
            # Now send back the challenge response
            logger.info('EXEC got a return from challenge ask from %s: %s' % (node['name'], cid))
            try:
                private_key = get_encrypter().get_mf_priv_key()
                RSA = encrypter.get_RSA()
                response = RSA.decrypt(challenge, private_key)
            except Exception as exp:
                err = 'EXEC bad challenge encoding from %s:%s (challenge type:%s)' % (node['name'], exp, type(challenge))
                execution_result['state'] = 'error'
                return execution_result
            
            response64 = string_to_b64unicode(response)
            payload = {'type': EXECUTER_PACKAGE_TYPES.CHALLENGE_RETURN, 'fr': gossiper.uuid,
                       'cid' : cid, 'response': response64,
                       'cmd' : command}
            
            packet = jsoner.dumps(payload)
            enc_packet = encrypter.encrypt(packet)
            logger.info('EXEC: sending a challenge response to %s' % node['name'])
            sock.sendto(enc_packet, (node['addr'], node['port']))
            
            # Now wait a return from this node exec
            sock.settimeout(5)
            try:
                raw = sock.recv(1024)
            except socket.timeout as exp:
                logger.error('EXEC done return timeout from node %s : %s (after %ss)' % (node['name'], exp, 5))
                execution_result['state'] = 'error'
                err = '(timeout after %ss)' % 5
                execution_result['output'] = err
                execution_result['err'] = err
                return execution_result
            
            msg = encrypter.decrypt(raw)
            if msg is None:
                logger.error('EXEC bad return from node %s' % node['name'])
                execution_result['state'] = 'error'
                err = '(node communication fail due to encryption error)'
                execution_result['output'] = err
                execution_result['err'] = err
                return execution_result
            
            try:
                ret = jsoner.loads(msg)
            except ValueError as exp:
                logger.error('EXEC bad return from node %s : %s' % (node['name'], exp))
                execution_result['state'] = 'error'
                err = '(node communication fail due to bad message: %s)' % msg
                execution_result['output'] = err
                execution_result['err'] = err
                return execution_result
            
            cid = ret.get('cid', '')  # challenge id
            if not cid:  # bad return?
                logger.error('EXEC bad return from node %s : no cid' % node['name'])
                execution_result['state'] = 'error'
                return execution_result
            
            v = kvmgr.get_key('__exec/%s' % execution_id)
            if v is None:
                logger.error('EXEC void KV entry from return from %s and cid %s' % (node['name'], execution_id))
                execution_result['state'] = 'error'
                err = '(error due to no returns from the other node)'
                execution_result['output'] = err
                execution_result['err'] = err
                return execution_result
            
            try:
                t = jsoner.loads(v)
            except ValueError as exp:
                logger.error('EXEC bad json entry return from %s and cid %s: %s' % (node['name'], cid, exp))
                execution_result['state'] = 'error'
                err = '(error due to bad returns from the other node: %s)' % v
                execution_result['output'] = err
                execution_result['err'] = err
                return execution_result
            
            logger.info('EXEC GOT A RETURN! %s %s %s %s' % (node['name'], cid, t['rc'], t['output']))
            execution_result['state'] = 'done'
            execution_result['output'] = t['output']
            execution_result['err'] = t['err']
            execution_result['rc'] = t['rc']
            return execution_result
    
    
    ############## Http interface
    # We must create http callbacks in running because
    # we must have the self object
    def export_http(self):
        from .httpdaemon import http_export, response, abort, request
        
        @http_export('/exec/:group')
        def launch_exec(group='*'):
            response.content_type = 'application/json'
            private_key = get_encrypter().get_mf_priv_key()
            if private_key is None:
                return abort(400, 'No master private key')
            if not topiker.is_topic_enabled(TOPIC_CONFIGURATION_AUTOMATION):
                return abort(400, 'Configuration automation is not allowed for this node')
            cmd_64 = request.GET.get('cmd', None)
            if cmd_64 is None:
                return abort(400, 'Missing parameter cmd')
            try:
                cmd = b64_into_unicode(cmd_64)  # base64 is giving bytes
            except ValueError:
                return abort(400, 'The parameter cmd is malformed, must be valid base64')
            uid = self.launch_exec(cmd, group)
            return jsoner.dumps(uid)
        
        
        @http_export('/exec-get/:exec_id')
        def get_exec(exec_id):
            response.content_type = 'application/json'
            return self.execs[exec_id]


executer = Executer()
