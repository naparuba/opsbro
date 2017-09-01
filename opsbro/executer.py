import json
import socket
import uuid as libuuid
import base64
import os
import time
import subprocess

from opsbro.encrypter import encrypter, RSA
from opsbro.log import LoggerFactory
from opsbro.threadmgr import threader
from opsbro.gossip import gossiper
from opsbro.kv import kvmgr
from opsbro.httpdaemon import http_export, response, abort, request

# Global logger for this part
logger = LoggerFactory.create_logger('executer')


class Executer(object):
    def __init__(self):
        # Execs launch as threads
        self.execs = {}
        # Challenge send so we can match the response when we will get them
        self.challenges = {}
    
    
    def load(self, mfkey_pub, mfkey_priv):
        self.mfkey_pub = mfkey_pub
        self.mfkey_priv = mfkey_priv
    
    
    def manage_exec_challenge_ask_message(self, m, addr):
        # If we don't have the public key, bailing out now
        if self.mfkey_pub is None:
            logger.debug('EXEC skipping exec call because we do not have a public key')
            return
        # get the with execution id from ask
        exec_id = m.get('exec_id', None)
        if exec_id is None:
            return
        cid = libuuid.uuid1().get_hex()  # challgenge id
        challenge = libuuid.uuid1().get_hex()
        e = {'ctime': int(time.time()), 'challenge': challenge, 'exec_id': exec_id}
        self.challenges[cid] = e
        # return a tuple with only the first element useful (str)
        # TOCLEAN:: _c = self.mfkey_pub.encrypt(challenge, 0)[0] # encrypt 0=dummy param not used
        _c = RSA.encrypt(challenge, self.mfkey_pub)  # encrypt 0=dummy param not used
        echallenge = base64.b64encode(_c)
        ping_payload = {'type': '/exec/challenge/proposal', 'fr': gossiper.uuid, 'challenge': echallenge, 'cid': cid}
        message = json.dumps(ping_payload)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        enc_message = encrypter.encrypt(message)
        logger.debug('EXEC asking us a challenge, return %s(%s) to %s' % (challenge, echallenge, addr))
        sock.sendto(enc_message, addr)
        sock.close()
    
    
    def manage_exec_challenge_return_message(self, m, addr):
        # Don't even look at it if we do not have a public key....
        if self.mfkey_pub is None:
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
            response = base64.b64decode(response64)
        except ValueError:
            logger.debug('EXEC invalid base64 response from %s' % addr)
            return
        
        logger.debug('EXEC got a challenge return from %s for %s:%s' % (_from, cid, response))
        # now try to decrypt the response of the other
        # This function take a tuple of size=2, but only look at the first...
        if response == p['challenge']:
            logger.debug('EXEC GOT GOOD FROM A CHALLENGE, DECRYPTED DATA', cid, response, p['challenge'],
                         response == p['challenge'])
            threader.create_and_launch(self.do_launch_exec, name='do-launch-exec-%s' % exec_id, args=(cid, exec_id, cmd, addr), part='executer')
    
    
    # Someone ask us to launch a new command (was already auth by RSA keys)
    def do_launch_exec(self, cid, exec_id, cmd, addr):
        logger.debug('EXEC launching a command %s' % cmd)
        
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, preexec_fn=os.setsid)
        output, err = p.communicate()  # Will lock here
        rc = p.returncode
        logger.debug("EXEC RETURN for command %s : %s %s %s" % (cmd, rc, output, err))
        o = {'output': output, 'rc': rc, 'err': err, 'cmd': cmd}
        j = json.dumps(o)
        # Save the return and put it in the KV space
        key = '__exec/%s' % exec_id
        kvmgr.put_key(key, j, ttl=3600)  # only one hour live is good :)
        
        # Now send a finish to the asker
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = {'type': '/exec/done', 'exec_id': exec_id, 'cid': cid}
        packet = json.dumps(payload)
        enc_packet = encrypter.encrypt(packet)
        logger.debug('EXEC: sending a exec done packet to %s:%s' % addr)
        logger.debug('EXEC: sending a exec done for the execution %s and the challenge id %s' % (exec_id, cid))
        try:
            sock.sendto(enc_packet, addr)
            sock.close()
        except Exception:
            sock.close()
    
    
    # Launch an exec thread and save its uuid so we can keep a look at it then
    def launch_exec(self, cmd, group):
        uid = libuuid.uuid1().get_hex()
        logger.debug('EXEC ask for launching command', cmd)
        all_uuids = []
        with gossiper.nodes_lock:  # get the nodes that follow the group (or all in *)
            for (uuid, n) in gossiper.nodes.iteritems():
                if (group == '*' or group in n['groups']) and n['state'] == 'alive':
                    exec_id = libuuid.uuid1().get_hex()  # to get back execution id
                    all_uuids.append((uuid, exec_id))
        
        e = {'cmd': cmd, 'group': group, 'thread': None, 'res': {}, 'nodes': all_uuids, 'ctime': int(time.time())}
        self.execs[uid] = e
        threader.create_and_launch(self.do_exec_thread, name='exec-%s' % uid, args=(e,), essential=True, part='executer')
        return e
    
    
    # Look at all nodes, ask them a challenge to manage with our priv key (they all got
    # our pub key)
    def do_exec_thread(self, e):
        # first look at which command we need to run
        cmd = e['cmd']
        logger.debug('EXEC ask for launching command', cmd)
        all_uuids = e['nodes']
        logger.debug('WILL EXEC command for %s' % all_uuids)
        for (nuid, exec_id) in all_uuids:
            node = gossiper.get(nuid)
            logger.debug('WILL EXEC A NODE? %s' % node)
            if node is None:  # was removed, don't play lotery today...
                continue
            # Get a socket to talk with this node
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            d = {'node': node, 'challenge': '', 'state': 'pending', 'rc': 3, 'output': '', 'err': ''}
            e['res'][nuid] = d
            logger.debug('EXEC asking for node %s' % node['name'])
            
            payload = {'type': '/exec/challenge/ask', 'fr': gossiper.uuid, 'exec_id': exec_id}
            packet = json.dumps(payload)
            enc_packet = encrypter.encrypt(packet)
            logger.debug('EXEC: sending a challenge request to %s' % node['name'])
            sock.sendto(enc_packet, (node['addr'], node['port']))
            # Now wait for a return
            sock.settimeout(3)
            try:
                raw = sock.recv(1024)
            except socket.timeout, exp:
                logger.error('EXEC challenge ask timeout from node %s : %s' % (node['name'], exp))
                sock.close()
                d['state'] = 'error'
                continue
            msg = encrypter.decrypt(raw)
            if msg is None:
                logger.error('EXEC bad return from node %s' % node['name'])
                sock.close()
                d['state'] = 'error'
                continue
            try:
                ret = json.loads(msg)
            except ValueError, exp:
                logger.error('EXEC bad return from node %s : %s' % (node['name'], exp))
                sock.close()
                d['state'] = 'error'
                continue
            cid = ret.get('cid', '')  # challenge id
            challenge64 = ret.get('challenge', '')
            if not challenge64 or not cid:
                logger.error('EXEC bad return from node %s : no challenge or challenge id' % node['name'])
                sock.close()
                d['state'] = 'error'
                continue
            try:
                challenge = base64.b64decode(challenge64)
            except ValueError:
                logger.error('EXEC bad return from node %s : invalid base64' % node['name'])
                sock.close()
                d['state'] = 'error'
                continue
            # Now send back the challenge response # dumy: add real RSA cypher here of course :)
            logger.debug('EXEC got a return from challenge ask from %s: %s' % (node['name'], cid))
            try:
                ##TOCLEAN:: response = self.mfkey_priv.decrypt(challenge)
                response = RSA.decrypt(challenge, self.mfkey_priv)
            except Exception, exp:
                logger.error('EXEC bad challenge encoding from %s:%s' % (node['name'], exp))
                sock.close()
                d['state'] = 'error'
                continue
            response64 = base64.b64encode(response)
            payload = {'type': '/exec/challenge/return', 'fr': gossiper.uuid,
                       'cid' : cid, 'response': response64,
                       'cmd' : cmd}
            packet = json.dumps(payload)
            enc_packet = encrypter.encrypt(packet)
            logger.debug('EXEC: sending a challenge response to %s' % node['name'])
            sock.sendto(enc_packet, (node['addr'], node['port']))
            
            # Now wait a return from this node exec
            sock.settimeout(3)
            try:
                raw = sock.recv(1024)
            except socket.timeout, exp:
                logger.error('EXEC done return timeout from node %s : %s' % (node['name'], exp))
                sock.close()
                d['state'] = 'error'
                continue
            msg = encrypter.decrypt(raw)
            if msg is None:
                logger.error('EXEC bad return from node %s' % node['name'])
                sock.close()
                d['state'] = 'error'
                continue
            try:
                ret = json.loads(msg)
            except ValueError, exp:
                logger.error('EXEC bad return from node %s : %s' % (node['name'], exp))
                sock.close()
                d['state'] = 'error'
                continue
            cid = ret.get('cid', '')  # challenge id
            if not cid:  # bad return?
                logger.error('EXEC bad return from node %s : no cid' % node['name'])
                d['state'] = 'error'
                continue
            v = kvmgr.get_key('__exec/%s' % exec_id)
            if v is None:
                logger.error('EXEC void KV entry from return from %s and cid %s' % (node['name'], exec_id))
                d['state'] = 'error'
                continue
            
            try:
                t = json.loads(v)
            except ValueError, exp:
                logger.error('EXEC bad json entry return from %s and cid %s: %s' % (node['name'], cid, exp))
                d['state'] = 'error'
                continue
            logger.debug('EXEC GOT A RETURN! %s %s %s %s' % (node['name'], cid, t['rc'], t['output']))
            d['state'] = 'done'
            d['output'] = t['output']
            d['err'] = t['err']
            d['rc'] = t['rc']
    
    
    ############## Http interface
    # We must create http callbacks in running because
    # we must have the self object
    def export_http(self):
        
        @http_export('/exec/:group')
        def launch_exec(group='*'):
            response.content_type = 'application/json'
            if self.mfkey_priv is None:
                return abort(400, 'No master private key')
            cmd = request.GET.get('cmd', 'uname -a')
            uid = self.launch_exec(cmd, group)
            return uid
        
        
        @http_export('/exec-get/:exec_id')
        def get_exec(exec_id):
            response.content_type = 'application/json'
            v = kvmgr.get_key('__exec/%s' % exec_id)
            return v  # can be None


executer = Executer()
