import socket
import json
import uuid as libuuid
import time
import random
import math
import requests as rq
import copy
import sys
import bisect

# some singleton :)
from kunai.log import logger
from kunai.threadmgr import threader
from kunai.broadcast import broadcaster
from kunai.websocketmanager import websocketmgr
from kunai.pubsub import pubsub
from kunai.httpdaemon import route, response, abort, request
from kunai.encrypter import encrypter
from kunai.httpclient import HTTP_EXCEPTIONS
from kunai.zonemanager import zonemgr
from kunai.stop import stopper

KGOSSIP = 10


# Main class for a Gossip cluster
class Gossip(object):
    def __init__(self):
        pass
    
    
    def init(self, nodes, nodes_lock, addr, port, name, display_name, incarnation, uuid, tags, seeds, bootstrap, zone, is_proxy):
        self.nodes = nodes
        self.nodes_lock = nodes_lock
        self.addr = addr
        self.port = port
        self.name = name
        self.display_name = display_name
        self.incarnation = incarnation
        self.uuid = uuid
        self.tags = tags  # finally computed tags
        self.detected_tags = set()  # tags from detectors, used to detect which to add/remove
        self.seeds = seeds
        self.bootstrap = bootstrap
        self.zone = zone
        self.is_proxy = is_proxy
        
        # list of uuid to ping back because we though they were dead
        self.to_ping_back = []
        
        # We update our nodes list based on our current zone. We keep our zone, only proxy from top zone
        # and all the sub zones
        self.clean_nodes_from_zone()
        
        # export my http uri now I got a real self
        self.export_http()
        
        self.ping_another_in_progress = False
        
        # create my own object, but do not export it to other nodes
        self.register_myself()
    
    
    def __getitem__(self, uuid):
        return self.nodes[uuid]
    
    
    # We should clean nodes that are not from our zone or direct top/sub one
    # and for:
    # * our zone: all nodes
    # * top zone: only proxy nodes
    # * sub zones: all nodes
    def clean_nodes_from_zone(self):
        if not self.zone:
            return
        
        to_del = []
        # direct top and sub zones are interesting
        top_zones = zonemgr.get_top_zones_from(self.zone)
        sub_zones = zonemgr.get_sub_zones_from(self.zone)
        with self.nodes_lock:
            for (nuuid, node) in self.nodes.iteritems():
                nzone = node['zone']
                # My zone, we keep
                if nzone == self.zone:
                    continue
                # Sub zones: keep all
                elif nzone in sub_zones:
                    continue
                # Top zones: keep only proxy nodes
                elif nzone in top_zones:
                    if node['is_proxy']:
                        continue  # you are saved
                    # you are not saved ^^
                    to_del.append(nuuid)
                # TODO: manage multi zone layer
                # Other zone, or unknown
                else:
                    to_del.append(nuuid)
            if len(to_del) > 0:
                logger.info("We have %d dirty nodes to remove because their zone is not valid from our own zone (%s)" % (len(to_del), self.zone))
            for nuuid in to_del:
                node = self.nodes[nuuid]
                logger.info('CLEANING dirty zone node: %s/%s (was in zone %s)' % (nuuid, node['name'], node['zone']))
                del self.nodes[nuuid]
    
    
    def get(self, uuid, default=None):
        return self.nodes.get(uuid, default)
    
    
    def __iter__(self):
        return self.nodes.__iter__()
    
    
    def __contains__(self, uuid):
        return uuid in self.nodes
    
    
    def __setitem__(self, k, value):
        self.nodes[k] = value
    
    
    def __delitem__(self, k):
        try:
            del self.nodes[k]
        except IndexError:
            pass
    
    
    def register_myself(self):
        myself = self.get_boostrap_node()
        self.set_alive(myself, bootstrap=True)
    
    
    def have_tag(self, tag):
        return tag in self.tags


    # find all nearly alive nodes with a specific tag
    def find_tag_nodes(self, tag):
        nodes = []
        with self.nodes_lock:
            for (uuid, node) in self.nodes.iteritems():
                if node['state'] in ['dead', 'leave']:
                    continue
                tags = node['tags']
                if tag in tags:
                    nodes.append(uuid)
        return nodes


    # find the good ring node for a tag and for a key
    def find_tag_node(self, tag, hkey):
        tag_nodes = self.find_tag_nodes(tag)
    
        # No kv nodes? oups, set myself so
        if len(tag_nodes) == 0:
            return self.uuid
    
        tag_nodes.sort()
    
        idx = bisect.bisect_right(tag_nodes, hkey) - 1
        # logger.debug("IDX %d" % idx, hkey, kv_nodes, len(kv_nodes))
        nuuid = tag_nodes[idx]
        return nuuid
    
    
    def count(self, state=''):
        with self.nodes_lock:
            if state:
                return len([n for n in self.nodes.values() if n['state'] == state])
            else:  # no filter, take all
                return len(self.nodes)
        
    
    # Another module/part did give a new tag, take it and warn others node about this
    # change if there is really a change
    def update_detected_tags(self, detected_tags):
        # if no change, we finish, job done
        if self.detected_tags == detected_tags:
            return
        logger.debug('We have an update for the detected tags. TAGS=%s  old-detected_tags=%s new-detected_tags=%s' % (self.tags, self.detected_tags, detected_tags))
        # ok here we will change things
        did_change = False
        new_tags = detected_tags - self.detected_tags
        deleted_tags = self.detected_tags - detected_tags
        # ok now we can take the new values
        self.detected_tags = detected_tags
        
        for tag in new_tags:
            if tag not in self.tags:
                did_change = True
                self.tags.append(tag)
                logger.info("New tag detected from detector for this node: %s" % tag, part='detector')
        for tag in deleted_tags:
            if tag in self.tags:
                did_change = True
                self.tags.remove(tag)
                logger.info("Tag was lost from the previous detection for this node: %s" % tag, part='detector')
        # warn other parts only if need
        if did_change:
            self.node_did_change(self.uuid)  # a node did change: ourselve
            self.increase_incarnation_and_broadcast(broadcast_type='alive')
        
        return did_change
    
    
    # A check did change it's state, update it in our structure
    def update_check_state_id(self, cname, state_id):
        node = self.nodes[self.uuid]
        if cname not in node['checks']:
            node['checks'][cname] = {'state_id': 3}
        node['checks'][cname]['state_id'] = state_id
    
    
    # We did have a massive change or a bad information from network, we must
    # fix this and warn others about good information
    def increase_incarnation_and_broadcast(self, broadcast_type=None):
        self.incarnation += 1
        node = self.nodes[self.uuid]
        node['incarnation'] = self.incarnation
        if broadcast_type == 'alive':
            self.stack_alive_broadcast(node)
        elif broadcast_type == 'leave':
            self.stack_leave_broadcast(node)
        else:
            logger.error('Asking for an unknown broadcast type for node: %s => %s' % (node, broadcast_type))
            sys.exit(2)
        logger.info('Did have to send a new incarnation node for myself. New incarnation=%d new-node=%s' % (self.incarnation, node), part='gossip')
    
    
    def change_zone(self, zname):
        self.zone = zname
        self.nodes[self.uuid]['zone'] = zname
        # let the others nodes know it
        self.increase_incarnation_and_broadcast('alive')
        # As we did change, we need to update our own node list to keep only what we should
        self.clean_nodes_from_zone()
    
    
    # get my own node entry
    def get_boostrap_node(self):
        node = {'addr'       : self.addr, 'port': self.port, 'name': self.name, 'display_name': self.display_name,
                'incarnation': self.incarnation, 'uuid': self.uuid, 'state': 'alive', 'tags': self.tags,
                'services'   : {}, 'checks': {}, 'zone': self.zone, 'is_proxy': self.is_proxy}
        return node
    
    
    # Definitivly remove a node from our list, and warn others about it
    def delete_node(self, nid):
        try:
            del self.nodes[nid]
            pubsub.pub('delete-node', node_uuid=nid)
        except IndexError:  # not here? it was was we want
            pass
    
    
    # Got a new node, great! Warn others about this
    # but if it's a bootstrap, only change memory, do not export to other nodes
    def add_new_node(self, node, bootstrap=False):
        logger.info("New node detected", node, part='gossip')
        nuuid = node['uuid']
        # Add the node but in a protected mode
        with self.nodes_lock:
            self.nodes[nuuid] = node
        # if bootstrap, do not export to other nodes or modules
        if bootstrap:
            return
        # Warn network elements
        self.stack_alive_broadcast(node)
        # And finally callback other part of the code about this
        pubsub.pub('new-node', node_uuid=nuuid)
        return
    
    
    # Warn other about a node that is not new or remove, but just did change it's internals data
    def node_did_change(self, nid):
        pubsub.pub('change-node', node_uuid=nid)
    
    
    ############# Main new state handling methods
    
    # Set alive a node we eart about. 
    # * It can be us if we allow the bootstrap node (only at startup).
    # * If strong it means we did the check, so we believe us :)
    def set_alive(self, node, bootstrap=False, strong=False):
        name = node['name']
        incarnation = node['incarnation']
        uuid = node['uuid']
        state = node['state'] = 'alive'
        
        # Maybe it's me? we must look for a specilal case:
        # maybe we did clean all our local data, and the others did remember us (we did keep
        # our uuid). But then we will never update our information. so we must increase our
        # incarnation to be the new master on our own information
        if not bootstrap:
            if node['uuid'] == self.uuid:
                if incarnation > self.incarnation:
                    # set as must as them
                    self.incarnation = incarnation
                    # and increase it to be the new master
                    self.increase_incarnation_and_broadcast(broadcast_type='alive')
                return
        
        # Maybe it's a new node that just enter the cluster?
        if uuid not in self.nodes:
            self.add_new_node(node, bootstrap=bootstrap)
            return
        
        prev = self.nodes.get(uuid, None)
        # maybe the prev was out by another thread?
        if prev is None:
            return
        change = (prev['state'] != state)
        
        # If the data is not just new, bail out
        if not strong and incarnation <= prev['incarnation']:
            return
        
        logger.debug('ALIVENODE', name, prev['state'], state, strong, change, incarnation, prev['incarnation'], (strong and change), (incarnation > prev['incarnation']), part='gossip')
        # only react to the new data if they are really new :)
        if strong or incarnation > prev['incarnation']:
            # protect the nodes access with the lock so others threads are happy :)
            with self.nodes_lock:
                self.nodes[uuid] = node
            
            # Only broadcast if it's a new data from somewhere else
            if (strong and change) or incarnation > prev['incarnation']:
                logger.debug("Updating alive a node", prev, 'with', node, part='gossip')
                # warn internal elements
                self.node_did_change(uuid)
                # and external ones
                self.stack_alive_broadcast(node)
    
    
    # Someone suspect a node, so believe it
    def set_suspect(self, suspect):
        incarnation = suspect['incarnation']
        uuid = suspect['uuid']
        state = 'suspect'
        
        # Maybe we didn't even have this nodes in our list?
        if uuid not in self.nodes:
            return
        
        node = self.nodes.get(uuid, None)
        # Maybe it vanish by another threads?
        if node is None:
            return
        
        # Maybe this data is too old
        if incarnation < node['incarnation']:
            return
        
        # We only case about into about alive nodes, dead and suspect
        # are not interesting :)
        if node['state'] != 'alive':
            return
        
        # Maybe it's us?? We need to say FUCKING NO, I'm alive!!
        if uuid == self.uuid:
            logger.warning('SUSPECT: SOMEONE THINK I AM SUSPECT, BUT I AM ALIVE', part='gossip')
            self.increase_incarnation_and_broadcast(broadcast_type='alive')
            return
        
        logger.info('SUSPECTING: I suspect node %s' % node['name'], part='gossip')
        # Ok it's definitivly someone else that is now suspected, update this, and update it :)
        node['incarnation'] = incarnation
        node['state'] = state
        node['suspect_time'] = int(time.time())
        
        # warn internal elements
        self.node_did_change(uuid)
        # and external ones
        self.stack_suspect_broadcast(node)
    
    
    # Someone ask us about a leave node, so believe it
    # Leave node are about all states, so we don't filter by current state
    # if the incarnation is ok, we believe it
    def set_leave(self, leaved):
        incarnation = leaved['incarnation']
        uuid = leaved['uuid']
        state = 'leave'
        
        logger.debug('SET_LEAVE::', uuid, leaved['name'], part='gossip')
        
        # Maybe we didn't even have this nodes in our list?
        if uuid not in self.nodes:
            return
        
        node = self.nodes.get(uuid, None)
        # The node can vanish by another thread delete
        if node is None:
            return
        
        # Maybe we already know it's leaved, so don't update it
        if node['state'] == 'leave':
            return
        
        # If for me it must be with my own incarnation number so we are sure it's really us that should leave
        # and not 
        if uuid == self.uuid:
            if incarnation != node['incarnation']:
                logger.debug('Someone is beliving that we did leave. It is not our own incarnation, we dont care about it', part='gossip')
                return
        else:
            # If not for me, use the classic 'not already known' rule
            if incarnation < node['incarnation']:
                logger.debug('Dropping old information (leave) about a node', part='gossip')
                return
        
        print "SET LEAVE UUID and SELF.UUID", uuid, self.uuid
        # Maybe it's us?? If so we must send our broadcast and exit in few seconds
        if uuid == self.uuid:
            logger.info('LEAVE: someone is asking me for leaving.', part='gossip')
            self.increase_incarnation_and_broadcast(broadcast_type='leave')
            
            
            # Define a function that will wait 10s to let the others nodes know that we did leave
            # and then ask for a clean stop of the daemon
            def bailout_after_leave(self):
                logger.log('Bailing out in few seconds. I was put in leave state')
                time.sleep(10)
                logger.log('Exiting from a self leave message')
                # Will set self.interrupted = True to every thread that loop
                pubsub.pub('interrupt')
            
            
            threader.create_and_launch(bailout_after_leave, args=(self,))
            return
        
        logger.info('LEAVING: The node %s is leaving' % node['name'], part='gossip')
        # Ok it's definitivly someone else that is now suspected, update this, and update it :)
        node['incarnation'] = incarnation
        node['state'] = state
        node['leave_time'] = int(time.time())
        
        # warn internal elements
        self.node_did_change(uuid)
        # and external ones
        self.stack_leave_broadcast(node)
    
    
    # Someone suspect a node, so believe it
    def set_dead(self, suspect):
        incarnation = suspect['incarnation']
        uuid = suspect['uuid']
        state = 'dead'
        
        # Maybe we didn't even have this nodes in our list?
        if uuid not in self.nodes:
            return
        
        node = self.nodes.get(uuid, None)
        # The node can vanish
        if node is None:
            return
        
        # Maybe this data is too old
        if incarnation < node['incarnation']:
            return
        
        # We only case about into about alive nodes
        # * dead : we already know it
        # * suspect : we already did receive it
        # * leave : it is already out in a way
        if node['state'] != 'alive':
            return
        
        # Maybe it's us?? We need to say FUCKING NO, I'm alive!!
        if uuid == self.uuid:
            logger.warning('SUSPECT: SOMEONE THINK I AM SUSPECT, BUT I AM ALIVE', part='gossip')
            self.increase_incarnation_and_broadcast(broadcast_type='alive')
            return
        
        logger.info('DEAD: I put in dead node %s' % node['name'], part='gossip')
        # Ok it's definitivly someone else that is now suspected, update this, and update it :)
        node['incarnation'] = incarnation
        node['state'] = state
        node['suspect_time'] = int(time.time())
        
        # warn internal elements
        self.node_did_change(uuid)
        # and external ones
        self.stack_dead_broadcast(node)
    
    
    # Someone send us it's nodes, we are merging it with ours
    def merge_nodes(self, nodes):
        for (k, node) in nodes.iteritems():
            # Maybe it's me? bail out
            # if node['addr'] == self.addr and node['port'] == self.port:
            if node['uuid'] == self.uuid:
                logger.debug('SKIPPING myself node entry in merge nodes')
                continue
            
            state = node['state']
            
            # Try to incorporate it
            if state == 'alive':
                self.set_alive(node)
            # note: for dead, we never believe others for dead, we set suspect
            # and wait for timeout to finish
            elif state == 'dead' or state == 'suspect':
                self.set_suspect(node)
            elif state == 'leave':
                self.set_leave(node)
    
    
    # We cannot full sync with all nodes:
    # * must be alive
    # * not ourselve ^^
    # * all of our own zone
    # * top zone: only proxy node
    # * lower zone: NO: we don't initialize sync to lower zone, they will do it themselve
    def __get_valid_nodes_to_full_sync(self):
        with self.nodes_lock:
            nodes = copy.copy(self.nodes)
        top_zones = zonemgr.get_top_zones_from(self.zone)
        
        possible_nodes = []
        for n in nodes.values():
            # skip ourselve
            if n['uuid'] == self.uuid:
                continue
            # skip bad nodes, must be alive
            if n['state'] != 'alive':
                continue
            # if our zone, will be OK
            nzone = n['zone']
            if nzone != self.zone:
                # if not, must be a relay and in directly top or sub zone
                if not n['is_proxy']:
                    continue
                if nzone not in top_zones:
                    continue
            # Ok you match dear node ^^
            possible_nodes.append((n['addr'], n['port']))
        return possible_nodes
    
    
    # We will choose a random guy in our nodes that is alive, and
    # sync with it
    def launch_full_sync(self):
        logger.debug("Launch_full_sync:: all nodes %d" % len(self.nodes), part='gossip')
        possible_nodes = self.__get_valid_nodes_to_full_sync()
        
        if len(possible_nodes) >= 1:
            other = random.choice(possible_nodes)
            logger.debug("launch_full_sync::", other, part='gossip')
            self.do_push_pull(other)
            # else:
            #    print "NO OTHER ALIVE NODES !"
    
    
    # We will choose some node and send them gossip messages to propagate the data
    # because if they didnt already receive it, they will also gossip it
    # There are two cases:
    # * we are NOT a proxy node, we choose K (~10) nodes of our zone to send message, and that's all
    # * we ARE a proxy node:
    #   * we still choose K random nodes of our zone
    #   * and for each other TOP zone, we choose K nodes from the other zone to send them
    # NOTE/SECURITY: we DON'T send messages to bottom zones, because they don't need to know about the internal
    #       data/state of the upper zone, they only need to know about the public states, so the proxy nodes
    def launch_gossip(self):
        # There is no broadcast message to sent so bail out :)
        if len(broadcaster.broadcasts) == 0:
            return
        
        with self.nodes_lock:
            nodes = copy.copy(self.nodes)
        
        # First we need to send all message to the others TOP zone, and do not 'consume' messages
        # only our zone will consume them so we are sure they will disapear
        if self.is_proxy:
            top_zones = zonemgr.get_top_zones_from(self.zone)
            for zname in top_zones:
                # we don't care about leave node, but we need others to be proxy
                others = [n for n in nodes.values() if n['zone'] == zname and n['state'] != 'leave' and n['is_proxy'] == True]
                # Maybe there is no valid nodes for this zone, skip it
                if len(others) == 0:
                    continue
                # Limit the broadcast
                nb_dest = min(len(others), KGOSSIP)
                dests = random.sample(others, nb_dest)
                for dest in dests:
                    logger.info("launch_gossip:: topzone::%s  node::" % zname, dest['name'], part='gossip')
                    self.__do_gossip_push(dest, consume=False)
        
        # always send to our zone, but not for leave nodes
        others = [n for n in nodes.values() if n['uuid'] != self.uuid and n['zone'] == self.zone and n['state'] != 'leave']
        logger.debug("launch_gossip:: our zone nodes %d" % len(others), part='gossip')
        
        # Maybe every one is dead, if o bail out
        if len(others) == 0:
            return
        nb_dest = min(len(others), KGOSSIP)
        dests = random.sample(others, nb_dest)
        for dest in dests:
            logger.info("launch_gossip::  our own zone::%s" % self.zone, dest['name'], part='gossip')
            self.__do_gossip_push(dest, consume=True)
    
    
    # We cannot ping with all nodes:
    # * must be not leave, we can ping dead/suspect, to check if they are still not OK
    # * not ourselve ^^
    # * all of our own zone
    # * top zone: only proxy node and if we are a proxy node
    # * lower zone: only proxy node and if we are a proxy node
    def __get_valid_nodes_to_ping(self):
        with self.nodes_lock:
            nodes = copy.copy(self.nodes)
        # If we are a proxy, we are allowed to talk to other zone
        if self.is_proxy:
            top_zones = zonemgr.get_top_zones_from(self.zone)
            sub_zones = zonemgr.get_sub_zones_from(self.zone)
        else:
            top_zones = sub_zones = []
        possible_nodes = []
        for n in nodes.values():
            # skip ourselve
            if n['uuid'] == self.uuid:
                continue
            # for ping, only leave nodes are not available, we can try to ping dead/suspect
            # to know if they are still bad
            if n['state'] == 'leave':
                continue
            # if our zone, will be OK
            nzone = n['zone']
            if nzone != self.zone:
                # if not, must be a relay and in directly top or sub zone
                if not n['is_proxy']:
                    continue
                # only proxy nodes can be allowed to talk to others
                if not self.is_proxy:
                    continue
                if nzone not in top_zones and nzone not in sub_zones:
                    continue
            # Ok you match dear node ^^
            possible_nodes.append(n)
            logger.info('VALID node to ping %s' % n['name'], part='gossip')
        return possible_nodes
    
    
    # we ping some K random nodes, but in priority some nodes that we thouugh were deads
    # but talk to us
    # also exclude leave node, because thay said they are not here anymore ^^
    def ping_another(self):
        # Only launch one parallel ping in the same time, max2 if we have thread
        # that mess up with this flag :)
        if self.ping_another_in_progress:
            return
        self.ping_another_in_progress = True
        
        possible_nodes = self.__get_valid_nodes_to_ping()
        
        # first previously deads
        for uuid in self.to_ping_back:
            node = self.nodes.get(uuid, None)
            if node is None:
                continue
            self.__do_ping(node)
        # now reset it
        self.to_ping_back = []
        
        # Now we take one in all the others
        if len(possible_nodes) >= 1:
            other = random.choice(possible_nodes)
            self.__do_ping(other)
        # Ok we did finish to ping another
        self.ping_another_in_progress = False
    
    
    # Launch a ping to another node and if fail set it as suspect
    def __do_ping(self, other):
        ping_payload = {'type': 'ping', 'seqno': 0, 'node': other['uuid'], 'from': self.uuid}
        # print "PREPARE PING", ping_payload, other
        message = json.dumps(ping_payload)
        enc_message = encrypter.encrypt(message)
        addr = other['addr']
        port = other['port']
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            sock.sendto(enc_message, (addr, port))
            logger.debug('PING waiting %s ack message' % other['name'], part='gossip')
            # Allow 3s to get an answer
            sock.settimeout(3)
            ret = sock.recv(65535)
            logger.debug('PING got a return from %s' % other['name'], len(ret), part='gossip')
            # An aswer? great it is alive!
            self.set_alive(other, strong=True)
        except (socket.timeout, socket.gaierror), exp:
            logger.debug("PING: error joining the other node %s:%s : %s" % (addr, port, exp), part='gossip')
            logger.debug("PING: go indirect mode", part='gossip')
            with self.nodes_lock:
                possible_relays = [n for n in self.nodes.values() if
                                   n['uuid'] != self.uuid and n != other and n['state'] == 'alive']
            
            if len(possible_relays) == 0:
                logger.log("PING: no possible relays for ping", part='gossip')
                self.set_suspect(other)
            # Take at least 3 relays to ask ping
            relays = random.sample(possible_relays, min(len(possible_relays), 3))
            logger.debug('POSSIBLE RELAYS', relays)
            ping_relay_payload = {'type': 'ping-relay', 'seqno': 0, 'tgt': other['uuid'], 'from': self.uuid}
            message = json.dumps(ping_relay_payload)
            enc_message = encrypter.encrypt(message)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            for r in relays:
                try:
                    sock.sendto(enc_message, (r['addr'], r['port']))
                    logger.debug('PING waiting ack message', part='gossip')
                except socket.error, exp:
                    logger.error('Cannot send a ping relay to %s:%s' % (r['addr'], r['port']), part='gossip')
            # Allow 3s to get an answer from whatever relays got it
            sock.settimeout(3 * 2)
            try:
                ret = sock.recv(65535)
            except socket.timeout:
                # still noone succed to ping it? I suspect it
                self.set_suspect(other)
                sock.close()
                return
            msg = json.loads(ret)
            sock.close()
            logger.debug('PING: got an answer from a relay', msg, part='gossip')
            logger.debug('RELAY set alive', other['name'], part='gossip')
            # Ok it's no more suspected, great :)
            self.set_alive(other, strong=True)
        except socket.error, exp:
            logger.log("PING: cannot join the other node %s:%s : %s" % (addr, port, exp), part='gossip')
    
    
    # Randomly push some gossip broadcast messages and send them to
    # KGOSSIP others nodes
    # consume: if True (default) then a message will be decremented
    def __do_gossip_push(self, dest, consume=True):
        message = ''
        to_del = []
        stack = []
        tags = dest['tags']
        for b in broadcaster.broadcasts:
            # not a valid node for this message, skip it
            if 'tag' in b and b['tag'] not in tags:
                continue
            old_message = message
            # only delete message if we consume it (our zone)
            if consume:
                send = b['send']
                if send >= KGOSSIP:
                    to_del.append(b)
            bmsg = b['msg']
            stack.append(bmsg)
            message = json.dumps(stack)
            # Maybe we are now too large and we do not have just one
            # fucking big message, so we fail back to the old_message that was
            # in the good size and send it now
            if len(message) > 1400 and len(stack) != 1:
                message = old_message
                stack = stack[:-1]
                break
            # Increase message send number but only if we need to consume it (our zone send)
            if consume:
                # stack a sent to this broadcast message
                b['send'] += 1
        
        # Clean too much broadcasted messages
        for b in to_del:
            broadcaster.broadcasts.remove(b)
        
        # Void message? bail out
        if len(message) == 0:
            return
        
        addr = dest['addr']
        port = dest['port']
        # and go for it!
        try:
            enc_message = encrypter.encrypt(message)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            sock.sendto(enc_message, (addr, port))
            logger.debug('BROADCAST: sent %d message (len=%d) to %s:%s' % (len(stack), len(enc_message), addr, port), part='gossip')
        except (socket.timeout, socket.gaierror), exp:
            logger.debug("ERROR: cannot sent the message %s" % exp, part='gossip')
        try:
            sock.close()
        except Exception:
            pass
    
    
    # Will try to join a node cluster and do a push-pull with at least one of them
    def join(self):
        logger.log("We will try to join our seeds members", self.seeds, part='gossip')
        tmp = self.seeds
        others = []
        if not len(self.seeds):
            logger.log("No seeds nodes, I'm a bootstrap node?")
            return
        
        for e in tmp:
            elts = e.split(':')
            addr = elts[0]
            port = self.port
            if len(elts) > 1:
                port = int(elts[1])
            others.append((addr, port))
        random.shuffle(others)
        while True:
            logger.log('JOINING myself %s is joining %s nodes' % (self.name, others), part='gossip')
            nb = 0
            for other in others:
                nb += 1
                r = self.do_push_pull(other)
                
                # Do not merge with more than KGOSSIP distant nodes
                if nb > KGOSSIP:
                    continue
            # If we got enough nodes, we exit
            if len(self.nodes) != 1 or stopper.interrupted or self.bootstrap:
                return
            # Do not hummer the cpu....
            time.sleep(0.1)
    
    
    # Go launch a push-pull to another node. We will sync all our nodes
    # entries, and each other will be able to learn new nodes and so
    # launch gossip broadcasts if need
    # We push pull:
    # * our own zone
    # * the upper zone
    # * NEVER lower zone. They will connect to us
    def do_push_pull(self, other):
        with self.nodes_lock:
            nodes = copy.deepcopy(self.nodes)
        sub_zones = zonemgr.get_sub_zones_from(self.zone)
        nodes_to_send = {}
        for (nuuid, node) in nodes.iteritems():
            nzone = node['zone']
            if nzone != self.zone and nzone not in sub_zones:
                # skip this node
                continue
            # ok in the good zone (our or sub)
            nodes_to_send[nuuid] = node
        logger.debug('do_push_pull:: giving %s informations about nodes: %s' % (other[0], [n['name'] for n in nodes_to_send.values()]), part='gossip')
        m = {'type': 'push-pull-msg', 'ask-from-zone': self.zone, 'nodes': nodes_to_send}
        message = json.dumps(m)
        
        (addr, port) = other
        
        uri = 'http://%s:%s/agent/push-pull' % (addr, port)
        payload = {'msg': message}
        try:
            r = rq.get(uri, params=payload)
            logger.debug("push-pull response", r, part='gossip')
            try:
                back = json.loads(r.content)
            except ValueError, exp:
                logger.error('ERROR CONNECTING TO %s:%s' % other, exp, part='gossip')
                return False
            logger.debug('do_push_pull: get return from %s:%s' % (other[0], back), part='gossip')
            if 'nodes' not in back:
                logger.error('do_push_pull: back message do not have nodes entry: %s' % back)
                return False
            self.merge_nodes(back['nodes'])
            return True
        except HTTP_EXCEPTIONS, exp:
            logger.error('[push-pull] ERROR CONNECTING TO %s:%s' % other, exp, part='gossip')
            return False
    
    
    # An other node did push-pull us, and we did load it's nodes,
    # but now we should give back only nodes that the other zone
    # have the right:
    # * same zone as us: give all we know about
    # * top zone: CANNOT  be the case, because only lower zone ask upper zones
    # * sub zones: give only our zone proxy nodes
    #   * no the other nodes of my zones, they don't have to know my zone detail
    #   * not my top zones of course, same reason, even proxy nodes, they need to talk to me only
    #   * not the other sub zones of my, because they don't have to see which who I am linked (can be an other customer for example)
    def get_nodes_for_push_pull_response(self, other_node_zone):
        logger.debug('PUSH-PULL: get a push pull from a node zone: %s' % other_node_zone, part='gossip')
        # Same zone: give all we know about
        if other_node_zone == self.zone:
            logger.debug('PUSH-PULL same zone ask us, give back all we know about', part='gossip')
            with self.nodes_lock:
                nodes = copy.copy(self.nodes)
            return nodes
        
        # Ok look if in sub zones: if found, all they need to know is
        # my realm proxy nodes,
        sub_zones = zonemgr.get_sub_zones_from(self.zone)
        if other_node_zone in sub_zones:
            only_my_zone_proxies = {}
            with self.nodes_lock:
                for (nuuid, node) in self.nodes.iteritems():
                    if node['is_proxy'] and node['zone'] == self.zone:
                        only_my_zone_proxies[nuuid] = node
                        logger.debug('PUSH-PULL: give back data about proxy node: %s' % node['name'], part='gossip')
            return only_my_zone_proxies
        
        logger.warning('SECURITY: a node from an unallowed zone %s did ask us push_pull' % other_node_zone)
        return {}
    
    
    # suspect nodes are set with a suspect_time entry. If it's too old,
    # set the node as dead, and broadcast the information to everyone
    def look_at_deads(self):
        # suspect a node for 5 * log(n+1) * interval
        node_scale = math.ceil(math.log10(float(len(self.nodes) + 1)))
        probe_interval = 1
        suspicion_mult = 5
        suspect_timeout = suspicion_mult * node_scale * probe_interval
        leave_timeout = suspect_timeout * 3  # something like 30s
        
        # print "SUSPECT timeout", suspect_timeout
        now = int(time.time())
        with self.nodes_lock:
            for node in self.nodes.values():
                # Only look at suspect nodes of course...
                if node['state'] != 'suspect':
                    continue
                stime = node.get('suspect_time', now)
                if stime < (now - suspect_timeout):
                    logger.info("SUSPECT: NODE", node['name'], node['incarnation'], node['state'], "is NOW DEAD", part='gossip')
                    node['state'] = 'dead'
                    self.stack_dead_broadcast(node)
        
        # Now for leave nodes, this time we will really remove the entry from our nodes
        to_del = []
        with self.nodes_lock:
            for node in self.nodes.values():
                # Only look at suspect nodes of course...
                if node['state'] != 'leave':
                    continue
                ltime = node.get('leave_time', now)
                logger.debug("LEAVE TIME for node %s %s %s %s" % (node['name'], ltime, now - leave_timeout, (now - leave_timeout) - ltime), part='gossip')
                if ltime < (now - leave_timeout):
                    logger.info("LEAVE: NODE", node['name'], node['incarnation'], node['state'], "is now definitivly leaved. We remove it from our nodes", part='gossip')
                    to_del.append(node['uuid'])
        # now really remove them from our list :)
        for uuid in to_del:
            self.delete_node(uuid)
    
    
    def __get_node_basic_msg(self, node):
        return {
            'name'       : node['name'], 'display_name': node.get('display_name', ''),
            'addr'       : node['addr'], 'port': node['port'], 'uuid': node['uuid'],
            'incarnation': node['incarnation'], 'tags': node['tags'],
            'services'   : node['services'], 'checks': node['checks'],
            'zone'       : node.get('zone', ''), 'is_proxy': node.get('is_proxy', False),
        }
    
    
    ########## Message managment
    def create_alive_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = 'alive'
        r['state'] = 'alive'
        return r
    
    
    def create_event_msg(self, payload):
        return {'type'   : 'event', 'from': self.uuid, 'payload': payload, 'ctime': int(time.time()),
                'eventid': libuuid.uuid1().get_hex()}
    
    
    def create_suspect_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = 'suspect'
        r['state'] = 'suspect'
        return r
    
    
    def create_dead_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = 'dead'
        r['state'] = 'dead'
        return r
    
    
    def create_leave_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = 'leave'
        r['state'] = 'leave'
        return r
    
    
    def create_new_ts_msg(self, key):
        return {'type': '/ts/new', 'from': self.uuid, 'key': key}
    
    
    def stack_alive_broadcast(self, node):
        msg = self.create_alive_msg(node)
        b = {'send': 0, 'msg': msg}
        broadcaster.broadcasts.append(b)
        # Also send it to the websocket if there
        self.forward_to_websocket(msg)
        return
    
    
    def stack_event_broadcast(self, payload):
        msg = self.create_event_msg(payload)
        b = {'send': 0, 'msg': msg}
        broadcaster.broadcasts.append(b)
        return
    
    
    def stack_new_ts_broadcast(self, key):
        msg = self.create_new_ts_msg(key)
        b = {'send': 0, 'msg': msg, 'tags': 'ts'}
        broadcaster.broadcasts.append(b)
        return
    
    
    def stack_suspect_broadcast(self, node):
        msg = self.create_suspect_msg(node)
        b = {'send': 0, 'msg': msg}
        broadcaster.broadcasts.append(b)
        # Also send it to the websocket if there
        self.forward_to_websocket(msg)
        return b
    
    
    def stack_leave_broadcast(self, node):
        msg = self.create_leave_msg(node)
        b = {'send': 0, 'msg': msg}
        broadcaster.broadcasts.append(b)
        # Also send it to the websocket if there
        self.forward_to_websocket(msg)
        return b
    
    
    def stack_dead_broadcast(self, node):
        msg = self.create_dead_msg(node)
        b = {'send': 0, 'msg': msg}
        broadcaster.broadcasts.append(b)
        self.forward_to_websocket(msg)
        return b
    
    
    def forward_to_websocket(self, msg):
        websocketmgr.forward({'channel': 'gossip', 'payload': msg})
    
    
    ############## Http interface
    # We must create http callbacks in running because
    # we must have the self object
    def export_http(self):
        
        @route('/agent/name')
        def get_name():
            return self.nodes[self.uuid]['name']
        
        
        @route('/agent/uuid')
        def get_name():
            return self.uuid
        
        
        @route('/agent/leave/:nuuid')
        def set_node_leave(nuuid):
            node = None
            with self.nodes_lock:
                node = self.nodes.get(nuuid, None)
            if node is None:
                return abort(404, 'This node is not found')
            logger.log('PUTTING LEAVE the node %s' % node, part='http')
            self.set_leave(node)
            return
        
        
        @route('/agent/members')
        def agent_members():
            response.content_type = 'application/json'
            logger.debug("/agent/members is called", part='http')
            with self.nodes_lock:
                nodes = copy.copy(self.nodes)
            return nodes
        
        
        @route('/agent/join/:other')
        def agent_join(other):
            response.content_type = 'application/json'
            addr = other
            port = self.port
            if ':' in other:
                parts = other.split(':', 1)
                addr = parts[0]
                port = int(parts[1])
            tgt = (addr, port)
            logger.info("HTTP: agent join for %s:%s " % (addr, port), part='http')
            r = self.do_push_pull(tgt)
            logger.info("HTTP: agent join for %s:%s result:%s" % (addr, port, r), part='http')
            return json.dumps(r)
        
        
        @route('/agent/push-pull')
        def interface_push_pull():
            response.content_type = 'application/json'
            logger.debug("PUSH-PULL called by HTTP", part='gossip')
            data = request.GET.get('msg')
            
            msg = json.loads(data)
            # First: load nodes from the distant node
            t = msg.get('type', None)
            if t is None or t != 'push-pull-msg':  # bad message, skip it
                return
            self.merge_nodes(msg['nodes'])
            
            # And look where does the message came from: if it's the same
            # zone: we can give all, but it it's a lower zone, only give our proxy nodes informations
            nodes = self.get_nodes_for_push_pull_response(msg['ask-from-zone'])
            m = {'type': 'push-pull-msg', 'nodes': nodes}
            
            logger.debug("PUSH-PULL returning my own nodes", part='gossip')
            return json.dumps(m)


gossiper = Gossip()
