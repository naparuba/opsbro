import socket
import json
import uuid as libuuid
import time
import random
import math
import copy
import sys
import bisect
import threading
import os
import glob

# some singleton :)
from .log import LoggerFactory
from .threadmgr import threader
from .broadcast import broadcaster
from .websocketmanager import websocketmgr
from .pubsub import pubsub
from .httpdaemon import http_export, response, abort, request
from .library import libstore
from .httpclient import get_http_exceptions, httper
from .zonemanager import zonemgr
from .stop import stopper
from .util import make_dir
from .handlermgr import handlermgr
from .topic import topiker, TOPIC_SERVICE_DISCOVERY

KGOSSIP = 10

# LIMIT= 4 * math.ceil(math.log10(float(2 + 1)))

# Global logger for this part
logger = LoggerFactory.create_logger('gossip')


# Main class for a Gossip cluster
class Gossip(object):
    def __init__(self):
        pass
    
    
    def init(self, nodes, nodes_lock, addr, port, name, display_name, incarnation, uuid, groups, seeds, bootstrap, zone, is_proxy):
        self.nodes = nodes
        self.nodes_lock = nodes_lock
        self.addr = addr
        self.port = port
        self.name = name
        self.display_name = display_name
        self.incarnation = incarnation
        self.uuid = uuid
        self.groups = groups  # finally computed groups
        self.groups_lock = threading.RLock()
        self.detected_groups = set()  # groups from detectors, used to detect which to add/remove
        self.seeds = seeds
        self.bootstrap = bootstrap
        self.zone = zone
        self.is_proxy = is_proxy
        
        # list of uuid to ping back because we though they were dead
        self.to_ping_back = []
        
        # Our main events dict, should not be too old or we will delete them
        self.events_lock = threading.RLock()
        self.events = {}
        self.max_event_age = 30
        
        # We update our nodes list based on our current zone. We keep our zone, only proxy from top zone
        # and all the sub zones
        self.clean_nodes_from_zone()
        
        # export my http uri now I got a real self
        self.export_http()
        
        # When something change, we save it in the history
        self.history_directory = None
        self.__prepare_history_directory()  # the configmgr is ready at this state
        self.__current_history_entry = []
        self.__current_history_entry_lock = threading.RLock()
        
        # create my own object, but do not export it to other nodes
        self.register_myself()
    
    
    def __getitem__(self, uuid):
        return self.nodes[uuid]
    
    
    # each second we look for all old events in order to clean and delete them :)
    def __clean_old_events(self):
        now = int(time.time())
        to_del = []
        with self.events_lock:
            for (cid, e) in self.events.iteritems():
                ctime = e.get('ctime', 0)
                if ctime < now - self.max_event_age:
                    to_del.append(cid)
            
            for cid in to_del:
                try:
                    del self.events[cid]
                except IndexError:  # if already delete, we don't care
                    pass
    
    
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
                logger.info('CLEANING we are in zone %s so we are removing a node from a unmanaged/distant zone: %s/%s (was in zone %s)' % (self.zone, nuuid, node['name'], node['zone']))
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
    
    
    def is_in_group(self, group):
        with self.groups_lock:
            return group in self.groups
    
    
    def __prepare_history_directory(self):
        # Prepare the history
        from .configurationmanager import configmgr
        data_dir = configmgr.get_data_dir()
        self.history_directory = os.path.join(data_dir, 'nodes_history')
        logger.debug('Asserting existence of the nodes history directory: %s' % self.history_directory)
        if not os.path.exists(self.history_directory):
            make_dir(self.history_directory)
    
    
    def __write_history_entry(self):
        with self.__current_history_entry_lock:
            # Noting to do?
            if not self.__current_history_entry:
                return
            now = int(time.time())
            pth = os.path.join(self.history_directory, '%d.json' % now)
            logger.info('Saving new compliance history entry to %s' % pth)
            buf = json.dumps(self.__current_history_entry)
            with open(pth, 'w') as f:
                f.write(buf)
            # Now we can reset it
            self.__current_history_entry = []
    
    
    def get_history(self):
        r = []
        current_size = 0
        max_size = 1024 * 1024
        reg = self.history_directory + '/*.json'
        history_files = glob.glob(reg)
        # Get from the more recent to the older
        history_files.sort()
        history_files.reverse()
        
        # Do not send more than 1MB, but always a bit more, not less
        for history_file in history_files:
            epoch_time = int(os.path.splitext(os.path.basename(history_file))[0])
            with open(history_file, 'r') as f:
                e = json.loads(f.read())
            r.append({'date': epoch_time, 'entries': e})
            
            # If we are now too big, return directly
            size = os.path.getsize(history_file)
            current_size += size
            if current_size > max_size:
                # Give older first
                r.reverse()
                return r
        # give older first
        r.reverse()
        return r
    
    
    def __add_group_change_history_entry(self, group, action):
        node = self.nodes[self.uuid]
        history_entry = {'type': 'group-%s' % action,
                         'name': node['name'], 'display_name': node.get('display_name', ''),
                         'uuid': node['uuid'], 'group': group,
                         }
        
        with self.__current_history_entry_lock:
            self.__current_history_entry.append(history_entry)
    
    
    def __add_node_state_change_history_entry(self, node, old_state, new_state):
        history_entry = {'type': 'node-state-change',
                         'name': node['name'], 'display_name': node.get('display_name', ''),
                         'uuid': node['uuid'], 'old_state': old_state, 'state': new_state,
                         }
        logger.info('__add_node_state_change_history_entry:: %s' % history_entry)
        with self.__current_history_entry_lock:
            self.__current_history_entry.append(history_entry)
    
    
    def __add_node_zone_change_history_entry(self, node, old_zone, new_zone):
        history_entry = {'type': 'node-zone-change',
                         'name': node['name'], 'display_name': node.get('display_name', ''),
                         'uuid': node['uuid'], 'old_zone': old_zone, 'zone': new_zone,
                         }
        logger.info('__add_node_zone_change_history_entry:: %s' % history_entry)
        with self.__current_history_entry_lock:
            self.__current_history_entry.append(history_entry)
    
    
    # Each seconds we try to save a history entry (about add/remove groups, or new nodes)
    def do_history_save_loop(self):
        while not stopper.interrupted:
            self.__write_history_entry()
            time.sleep(1)
    
    
    def add_group(self, group, broadcast_when_change=True):
        did_change = False
        with self.groups_lock:
            if group not in self.groups:
                self.groups.append(group)
                # let the caller known that we did work
                did_change = True
                logger.info('The group %s was added.' % group)
            # If our groups did change and we did allow to broadcast here (like in CLI call but not in
            # auto discovery because we want to send only 1 network packet), we can broadcast it
            if did_change:
                # We always stack a history entry, it's only save once a seconds
                self.__add_group_change_history_entry(group, 'add')
                # Let the handlers known about it
                handlermgr.launch_group_handlers(group, 'add')
                # but not always network, must be done once a loop
                if broadcast_when_change:
                    self.node_did_change(self.uuid)  # a node did change: ourselve
                    self.increase_incarnation_and_broadcast(broadcast_type='alive')
        
        return did_change
    
    
    def remove_group(self, group, broadcast_when_change=True):
        did_change = False
        with self.groups_lock:
            if group in self.groups:
                self.groups.remove(group)
                # let the caller known that we did work
                logger.info('The group %s was removed.' % group)
                did_change = True
            # If our groups did change and we did allow to broadcast here (like in CLI call but not in
            # auto discovery because we want to send only 1 network packet), we can broadcast it
            if did_change:
                # We always stack a history entry, it's only save once a seconds
                self.__add_group_change_history_entry(group, 'remove')
                # Let the handlers known about it
                handlermgr.launch_group_handlers(group, 'remove')
                
                # but not always network, must be done once a loop
                if broadcast_when_change:
                    self.node_did_change(self.uuid)  # a node did change: ourselve
                    self.increase_incarnation_and_broadcast(broadcast_type='alive')
        return did_change
    
    
    # find all nearly alive nodes with a specific group
    def find_group_nodes(self, group):
        nodes = []
        with self.nodes_lock:
            for (uuid, node) in self.nodes.iteritems():
                if node['state'] in ['dead', 'leave']:
                    continue
                groups = node.get('groups', [])
                if group in groups:
                    nodes.append(uuid)
        return nodes
    
    
    # find the good ring node for a group and for a key
    def find_group_node(self, group, hkey):
        group_nodes = self.find_group_nodes(group)
        
        # No kv nodes? oups, set myself so
        if len(group_nodes) == 0:
            return self.uuid
        
        group_nodes.sort()
        
        idx = bisect.bisect_right(group_nodes, hkey) - 1
        # logger.debug("IDX %d" % idx, hkey, kv_nodes, len(kv_nodes))
        nuuid = group_nodes[idx]
        return nuuid
    
    
    def count(self, state=''):
        with self.nodes_lock:
            if state:
                return len([n for n in self.nodes.values() if n['state'] == state])
            else:  # no filter, take all
                return len(self.nodes)
    
    
    # Another module/part did give a new group, take it and warn others node about this
    # change if there is really a change
    def update_detected_groups(self, detected_groups):
        # if no change, we finish, job done
        if self.detected_groups == detected_groups:
            return
        logger.debug('We have an update for the detected groups. GROUPS=%s  old-detected_groups=%s new-detected_groups=%s' % (self.groups, self.detected_groups, detected_groups))
        # ok here we will change things
        did_change = False
        new_groups = detected_groups - self.detected_groups
        deleted_groups = self.detected_groups - detected_groups
        # ok now we can take the new values
        self.detected_groups = detected_groups
        
        for group in new_groups:
            if not self.is_in_group(group):
                did_change = True
                # We do not want to send a boardcast now, we have still other group to manage
                # and send only one change
                self.add_group(group, broadcast_when_change=False)
                logger.info("New group detected from detector for this node: %s" % group)
        for group in deleted_groups:
            if self.is_in_group(group):
                did_change = True
                # We do not want to send a boardcast now, we have still other group to manage
                # and send only one change
                self.remove_group(group, broadcast_when_change=False)
                logger.info("Group was lost from the previous detection for this node: %s" % group)
        # warn other parts only if need, and do it only once even for lot of groups
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
        logger.info('Did have to send a new incarnation node for myself. New incarnation=%d new-node=%s' % (self.incarnation, node))
    
    
    def change_zone(self, zname):
        if self.zone == zname:
            return
        logger.info('Switching to zone: %s' % zname)
        self.zone = zname
        self.nodes[self.uuid]['zone'] = zname
        # let the others nodes know it
        self.increase_incarnation_and_broadcast('alive')
        # As we did change, we need to update our own node list to keep only what we should
        self.clean_nodes_from_zone()
    
    
    def get_zone_from_node(self, node_uuid=''):
        if not node_uuid:
            node_uuid = self.uuid
        node = self.nodes.get(node_uuid, None)
        if node is None:
            return ''
        node_zone = node.get('zone', '')
        logger.info('get_zone_from_node:: giving back %s' % node_zone)
        return node_zone
    
    
    def get_number_of_nodes(self):
        with self.nodes_lock:
            return len(self.nodes)
    
    
    # get my own node entry
    def get_boostrap_node(self):
        node = {'addr'       : self.addr, 'port': self.port, 'name': self.name, 'display_name': self.display_name,
                'incarnation': self.incarnation, 'uuid': self.uuid, 'state': 'alive', 'groups': self.groups,
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
    def __add_new_node(self, node, bootstrap=False):
        logger.info("New node detected", node)
        nuuid = node['uuid']
        node_zone = node['zone']
        
        # Maybe it's from another zone:
        # * top zone: we want only proxy nodes
        # * lower zones: all nodes are interesting
        if node_zone != self.zone:
            if zonemgr.is_top_zone_from(self.zone, node_zone):
                logger.debug('NEW NODE IS FROM A TOP ZONE')
                if not node['is_proxy']:
                    logger.info('A node from a top zone cannot be inserted unless is it a proxy node. Skiping the node %s' % nuuid)
                    return
        
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
        
        # Maybe it's me? we must look for a special case:
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
            self.__add_new_node(node, bootstrap=bootstrap)
            return
        
        prev = self.nodes.get(uuid, None)
        # maybe the prev was out by another thread?
        if prev is None:
            return
        prev_state = prev['state']
        change_state = (prev_state != state)
        
        # If the data is not just new, bail out
        if not strong and incarnation <= prev['incarnation']:
            return
        
        logger.debug('ALIVENODE', name, prev_state, state, strong, change_state, incarnation, prev['incarnation'], (strong and change_state), (incarnation > prev['incarnation']))
        # only react to the new data if they are really new :)
        if strong or incarnation > prev['incarnation']:
            # protect the nodes access with the lock so others threads are happy :)
            with self.nodes_lock:
                self.nodes[uuid] = node
            
            # Only broadcast if it's a new data from somewhere else
            if (strong and change_state) or incarnation > prev['incarnation']:
                logger.debug("Updating alive a node", prev, 'with', node)
                # warn internal elements
                self.node_did_change(uuid)
                # and external ones
                self.stack_alive_broadcast(node)
                if change_state:
                    # Save this change into our history
                    self.__add_node_state_change_history_entry(node, prev_state, node['state'])
    
    
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
        prev_state = node['state']
        if prev_state != 'alive':
            return
        
        # Maybe it's us?? We need to say FUCKING NO, I'm alive!!
        if uuid == self.uuid:
            logger.warning('SUSPECT: SOMEONE THINK I AM SUSPECT, BUT I AM ALIVE')
            self.increase_incarnation_and_broadcast(broadcast_type='alive')
            return
        
        logger.info('SUSPECTING: I suspect node %s' % node['name'])
        # Ok it's definitivly someone else that is now suspected, update this, and update it :)
        node['incarnation'] = incarnation
        node['state'] = state
        node['suspect_time'] = int(time.time())
        
        # warn internal elements
        self.node_did_change(uuid)
        # Save this change into our history
        self.__add_node_state_change_history_entry(node, prev_state, node['state'])
        # and external ones
        self.stack_suspect_broadcast(node)
    
    
    # Someone ask us about a leave node, so believe it
    # Leave node are about all states, so we don't filter by current state
    # if the incarnation is ok, we believe it
    def set_leave(self, leaved):
        incarnation = leaved['incarnation']
        uuid = leaved['uuid']
        state = 'leave'
        
        logger.info('SET_LEAVE::', uuid, leaved['name'], incarnation)
        
        # Maybe we didn't even have this nodes in our list?
        if uuid not in self.nodes:
            return
        
        node = self.nodes.get(uuid, None)
        # The node can vanish by another thread delete
        if node is None:
            return
        
        prev_state = node['state']
        # Maybe we already know it's leaved, so don't update it
        if prev_state == 'leave':
            return
        
        # If for me it must be with my own incarnation number so we are sure it's really us that should leave
        # and not 
        if uuid == self.uuid:
            if incarnation != node['incarnation']:
                logger.debug('Someone is beliving that we did leave. It is not our own incarnation, we dont care about it')
                return
        else:
            # If not for me, use the classic 'not already known' rule
            if incarnation < node['incarnation']:
                logger.info('Dropping old information (LEAVE) about a node (%s). Our memory incarnation: %s Message incarnation:%s' % (uuid, node['incarnation'], incarnation))
                return
        
        # Maybe it's us?? If so we must send our broadcast and exit in few seconds
        if uuid == self.uuid:
            logger.info('LEAVE: someone is asking me for leaving.')
            # Mark myself as leave so
            node['state'] = state
            self.increase_incarnation_and_broadcast(broadcast_type='leave')
            
            
            # Define a function that will wait 10s to let the others nodes know that we did leave
            # and then ask for a clean stop of the daemon
            def bailout_after_leave(self):
                wait_time = 10
                logger.info('Waiting out %s seconds before exiting as we are set in leave state' % wait_time)
                time.sleep(10)
                logger.info('Exiting from a self leave message')
                # Will set self.interrupted = True to every thread that loop
                pubsub.pub('interrupt')
            
            
            threader.create_and_launch(bailout_after_leave, args=(self,), name='Exiting agent after set to leave', part='agent')
            return
        
        logger.info('LEAVING: The node %s is leaving' % node['name'])
        # Ok it's definitivly someone else that is now suspected, update this, and update it :)
        node['incarnation'] = incarnation
        node['state'] = state
        node['leave_time'] = int(time.time())
        
        # warn internal elements
        self.node_did_change(uuid)
        # Save this change into our history
        self.__add_node_state_change_history_entry(node, prev_state, node['state'])
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
        prev_state = node['state']
        if prev_state != 'alive':
            return
        
        # Maybe it's us?? We need to say FUCKING NO, I'm alive!!
        if uuid == self.uuid:
            logger.warning('DEAD: SOMEONE THINK I AM DEAD, BUT I AM ALIVE')
            self.increase_incarnation_and_broadcast(broadcast_type='alive')
            return
        
        logger.info('DEAD: I put in dead node %s' % node['name'])
        # Ok it's definitivly someone else that is now suspected, update this, and update it :)
        node['incarnation'] = incarnation
        node['state'] = state
        node['suspect_time'] = int(time.time())
        
        # warn internal elements
        self.node_did_change(uuid)
        # Save this change into our history
        self.__add_node_state_change_history_entry(node, prev_state, node['state'])
        # and external ones
        self.stack_dead_broadcast(node)
    
    
    # Someone send us it's nodes, we are merging it with ours
    def merge_nodes(self, nodes):
        for (k, node) in nodes.iteritems():
            # Maybe it's me? bail out
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
                # if not, must be a relay and in directly top zone
                if not n['is_proxy']:
                    continue
                if nzone not in top_zones:
                    continue
            # Ok you match dear node ^^
            possible_nodes.append((n['addr'], n['port']))
        return possible_nodes
    
    
    # We will choose a random guy in our nodes that is alive, and
    # sync with it
    def launch_full_sync_loop(self):
        while not stopper.interrupted:
            # Only sync if we are allowed to do service discovery
            if topiker.is_topic_enabled(TOPIC_SERVICE_DISCOVERY):
                self.launch_full_sync()
            time.sleep(15)
    
    
    def launch_full_sync(self):
        logger.debug("Launch_full_sync:: all nodes %d" % len(self.nodes))
        possible_nodes = self.__get_valid_nodes_to_full_sync()
        
        if len(possible_nodes) >= 1:
            other = random.choice(possible_nodes)
            logger.debug("launch_full_sync::", other)
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
    def do_launch_gossip_loop(self):
        while not stopper.interrupted:
            if topiker.is_topic_enabled(TOPIC_SERVICE_DISCOVERY):
                self.launch_gossip()
            self.__clean_old_events()
            time.sleep(1)
    
    
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
                    logger.info("launch_gossip:: topzone::%s  node::" % zname, dest['name'])
                    self.__do_gossip_push(dest, consume=False)
        
        # always send to our zone, but not for leave nodes
        others = [n for n in nodes.values() if n['uuid'] != self.uuid and n['zone'] == self.zone and n['state'] != 'leave']
        logger.debug("launch_gossip:: our zone nodes %d" % len(others))
        
        # Maybe every one is dead, if o bail out
        if len(others) == 0:
            return
        nb_dest = min(len(others), KGOSSIP)
        dests = random.sample(others, nb_dest)
        for dest in dests:
            logger.info("launch_gossip::  our own zone::%s" % self.zone, dest['name'])
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
            logger.debug('VALID node to ping %s' % n['name'])
        return possible_nodes
    
    
    # THREAD: every second send a Gossip UDP ping to another node, random choice
    def ping_another_nodes(self):
        while not stopper.interrupted:
            if topiker.is_topic_enabled(TOPIC_SERVICE_DISCOVERY):
                self.ping_another()
            time.sleep(1)
    
    
    # we ping some K random nodes, but in priority some nodes that we thouugh were deads
    # but talk to us
    # also exclude leave node, because thay said they are not here anymore ^^
    def ping_another(self):
        # Only launch one parallel ping in the same time, max2 if we have thread
        # that mess up with this flag :)
        # if self.ping_another_in_progress:
        #    return
        # self.ping_another_in_progress = True
        
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
            # self.ping_another_in_progress = False
    
    
    # Launch a ping to another node and if fail set it as suspect
    def __do_ping(self, other):
        ping_payload = {'type': 'ping', 'seqno': 0, 'node': other['uuid'], 'from': self.uuid}
        # print "PREPARE PING", ping_payload, other
        message = json.dumps(ping_payload)
        encrypter = libstore.get_encrypter()
        enc_message = encrypter.encrypt(message)
        addr = other['addr']
        port = other['port']
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            sock.sendto(enc_message, (addr, port))
            logger.debug('PING waiting %s ack message' % other['name'])
            # Allow 3s to get an answer
            sock.settimeout(3)
            ret = sock.recv(65535)
            logger.debug('PING got a return from %s' % other['name'], len(ret))
            # An aswer? great it is alive!
            self.set_alive(other, strong=True)
        except (socket.timeout, socket.gaierror), exp:
            logger.debug("PING: error joining the other node %s:%s : %s" % (addr, port, exp))
            logger.debug("PING: go indirect mode")
            with self.nodes_lock:
                possible_relays = [n for n in self.nodes.values() if
                                   n['uuid'] != self.uuid and n != other and n['state'] == 'alive']
            
            if len(possible_relays) == 0:
                logger.log("PING: no possible relays for ping")
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
                    logger.debug('PING waiting ack message')
                except socket.error, exp:
                    logger.error('Cannot send a ping relay to %s:%s' % (r['addr'], r['port']))
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
            logger.debug('PING: got an answer from a relay', msg)
            logger.debug('RELAY set alive', other['name'])
            # Ok it's no more suspected, great :)
            self.set_alive(other, strong=True)
        except socket.error, exp:
            logger.log("PING: cannot join the other node %s:%s : %s" % (addr, port, exp))
    
    
    def manage_ping_message(self, m, addr):
        # if it me that the other is pinging? because it can think to
        # thing another but in my addr, like it I did change my name
        did_want_to_ping = m.get('node', None)
        if did_want_to_ping != self.uuid:  # not me? skip this
            return
        ack = {'type': 'ack', 'seqno': m['seqno']}
        ret_msg = json.dumps(ack)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        encrypter = libstore.get_encrypter()
        enc_ret_msg = encrypter.encrypt(ret_msg)
        sock.sendto(enc_ret_msg, addr)
        sock.close()
        logger.debug("PING RETURN ACK MESSAGE", ret_msg)
        # now maybe the source was a suspect that just ping me? if so
        # ask for a future ping
        fr_uuid = m['from']
        node = self.get(fr_uuid)
        if node and node['state'] != 'alive':
            logger.debug('PINGBACK +ing node', node['name'])
            self.to_ping_back.append(fr_uuid)
    
    
    # We are ask to do a indirect ping to tgt and return the ack to
    # _from, do this in a thread so we don't lock here
    def do_indirect_ping(self, tgt, _from, addr):
        logger.debug('do_indirect_ping', tgt, _from)
        ntgt = self.get(tgt, None)
        nfrom = self.get(_from, None)
        # If the dest or the from node are now unknown, exit this thread
        if not ntgt or not nfrom:
            return
        # Now do the real ping
        ping_payload = {'type': 'ping', 'seqno': 0, 'node': ntgt['name'], 'from': self.uuid}
        message = json.dumps(ping_payload)
        tgtaddr = ntgt['addr']
        tgtport = ntgt['port']
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            encrypter = libstore.get_encrypter()
            enc_message = encrypter.encrypt(message)
            sock.sendto(enc_message, (tgtaddr, tgtport))
            logger.debug('PING waiting %s ack message from a ping-relay' % ntgt['name'])
            # Allow 3s to get an answer
            sock.settimeout(3)
            ret = sock.recv(65535)
            logger.debug('PING (relay) got a return from %s' % ntgt['name'], ret)
            # An aswer? great it is alive! Let it know our _from node
            ack = {'type': 'ack', 'seqno': 0}
            ret_msg = json.dumps(ack)
            enc_ret_msg = encrypter.encrypt(ret_msg)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            sock.sendto(enc_ret_msg, addr)
            sock.close()
        except (socket.timeout, socket.gaierror):
            # cannot reach even us? so it's really dead, let the timeout do its job on _from
            pass
    
    
    def manage_ping_relay_message(self, m, addr):
        tgt = m.get('tgt')
        _from = m.get('from', '')
        if not tgt or not _from:
            return
        
        # Do the indirect ping as a sub-thread
        threader.create_and_launch(self.do_indirect_ping, name='indirect-ping-%s-%s' % (tgt, _from), args=(tgt, _from, addr), part='gossip')
    
    
    # A node did send us a discovery message but with the valid network key of course.
    # If so, give back our node informations
    def manage_detect_ping_message(self, m, addr):
        my_self = self.nodes[self.uuid]
        my_node_data = self.create_alive_msg(my_self)
        
        r = {'type': 'detect-pong', 'node': my_node_data}
        ret_msg = json.dumps(r)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        encrypter = libstore.get_encrypter()
        enc_ret_msg = encrypter.encrypt(ret_msg)
        sock.sendto(enc_ret_msg, addr)
        sock.close()
        logger.debug("Detect back: return back message", ret_msg)
    
    
    # launch a broadcast (UDP) and wait 5s for returns, and give all answers from others daemons
    def launch_gossip_detect_ping(self):
        r = []
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(5)
        p = '{"type":"detect-ping"}'
        encrypter = libstore.get_encrypter()
        enc_p = encrypter.encrypt(p)
        s.sendto(enc_p, ('<broadcast>', 6768))
        try:
            while True:
                data, addr = s.recvfrom(65507)
                try:
                    d_str = encrypter.decrypt(data)
                    d = json.loads(d_str)
                # If bad json, skip it
                except ValueError:
                    continue
                # if not a detect-pong package, I don't want it
                _type = d.get('type', '')
                if _type != 'detect-pong':
                    continue
                # Skip if not node in it
                if 'node' not in d:
                    continue
                # Maybe it's me, if so skip it
                n = d['node']
                nuuid = n.get('uuid', self.uuid)
                if nuuid == self.uuid:
                    continue
                r.append(n)
        except socket.timeout:
            pass
        return r
    
    
    # Randomly push some gossip broadcast messages and send them to
    # KGOSSIP others nodes
    # consume: if True (default) then a message will be decremented
    def __do_gossip_push(self, dest, consume=True):
        message = ''
        to_del = []
        stack = []
        groups = dest.get('groups', [])
        # Be sure we will have first:
        # * prioritary messages
        # * less send first
        broadcaster.sort()
        with broadcaster.broadcasts_lock:
            for b in broadcaster.broadcasts:
                # not a valid node for this message, skip it
                if 'group' in b and b['group'] not in groups:
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
                    logger.debug("__do_gossip_push:: overload message %s. skipping new ones" % len(stack))
                    break
                # Increase message send number but only if we need to consume it (our zone send)
                if consume:
                    # stack a sent to this broadcast message
                    b['send'] += 1
        
        with broadcaster.broadcasts_lock:
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
            encrypter = libstore.get_encrypter()
            enc_message = encrypter.encrypt(message)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            sock.sendto(enc_message, (addr, port))
            logger.info('BROADCAST: sent %d message (len=%d) to %s:%s (uuid=%s)' % (len(stack), len(enc_message), addr, port, dest['uuid']))
        except (socket.timeout, socket.gaierror), exp:
            logger.debug("ERROR: cannot sent the message %s" % exp)
        try:
            sock.close()
        except Exception:
            pass
    
    
    # Will try to join a node cluster and do a push-pull with at least one of them
    def join(self):
        logger.log("We will try to join our seeds members", self.seeds)
        tmp = self.seeds
        others = []
        if not len(self.seeds):
            logger.info("We do not have any seeds to join at startup.")
            return
        
        for e in tmp:
            elts = e.split(':')
            addr = elts[0]
            port = self.port
            if len(elts) > 1:
                port = int(elts[1])
            others.append((addr, port))
        random.shuffle(others)
        while not stopper.interrupted:
            logger.log('JOINING myself %s is joining %s nodes' % (self.name, others))
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
        logger.debug('do_push_pull:: giving %s informations about nodes: %s' % (other[0], [n['name'] for n in nodes_to_send.values()]))
        m = {'type': 'push-pull-msg', 'ask-from-zone': self.zone, 'nodes': nodes_to_send}
        message = json.dumps(m)
        
        (addr, port) = other
        
        uri = 'http://%s:%s/agent/push-pull' % (addr, port)
        payload = {'msg': message}
        try:
            r = httper.get(uri, params=payload)
            logger.debug("push-pull response", r)
            try:
                back = json.loads(r)
            except ValueError, exp:
                logger.error('ERROR CONNECTING TO %s:%s' % other, exp)
                return False
            logger.debug('do_push_pull: get return from %s:%s' % (other[0], back))
            if 'nodes' not in back:
                logger.error('do_push_pull: back message do not have nodes entry: %s' % back)
                return False
            self.merge_nodes(back['nodes'])
            return True
        except get_http_exceptions(), exp:
            logger.error('[push-pull] ERROR CONNECTING TO %s:%s' % other, exp)
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
        logger.debug('PUSH-PULL: get a push pull from a node zone: %s' % other_node_zone)
        # Same zone: give all we know about
        if other_node_zone == self.zone:
            logger.debug('PUSH-PULL same zone ask us, give back all we know about')
            with self.nodes_lock:
                nodes = copy.copy(self.nodes)
            return nodes
        
        # Ok look if in sub zones: if found, all they need to know is
        # my realm proxy nodes
        sub_zones = zonemgr.get_sub_zones_from(self.zone)
        if other_node_zone in sub_zones:
            only_my_zone_proxies = {}
            with self.nodes_lock:
                for (nuuid, node) in self.nodes.iteritems():
                    if node['is_proxy'] and node['zone'] == self.zone:
                        only_my_zone_proxies[nuuid] = node
                        logger.debug('PUSH-PULL: give back data about proxy node: %s' % node['name'])
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
        leave_timeout = suspect_timeout * 30  # something like 300s
        
        # print "SUSPECT timeout", suspect_timeout
        now = int(time.time())
        with self.nodes_lock:
            for node in self.nodes.values():
                # Only look at suspect nodes of course...
                if node['state'] != 'suspect':
                    continue
                stime = node.get('suspect_time', now)
                if stime < (now - suspect_timeout):
                    logger.info("SUSPECT: NODE", node['name'], node['incarnation'], node['state'], "is NOW DEAD")
                    node['state'] = 'dead'
                    # warn internal elements
                    self.node_did_change(node['uuid'])
                    # Save this change into our history
                    self.__add_node_state_change_history_entry(node, 'suspect', 'dead')
                    # and external ones
                    self.stack_dead_broadcast(node)
        
        # Now for leave nodes, this time we will really remove the entry from our nodes
        to_del = []
        with self.nodes_lock:
            for node in self.nodes.values():
                # Only look at suspect nodes of course...
                if node['state'] != 'leave':
                    continue
                ltime = node.get('leave_time', now)
                logger.debug("LEAVE TIME for node %s %s %s %s" % (node['name'], ltime, now - leave_timeout, (now - leave_timeout) - ltime))
                if ltime < (now - leave_timeout):
                    logger.info("LEAVE: NODE", node['name'], node['incarnation'], node['state'], "is now definitivly leaved. We remove it from our nodes")
                    to_del.append(node['uuid'])
        # now really remove them from our list :)
        for uuid in to_del:
            self.delete_node(uuid)
    
    
    def __get_node_basic_msg(self, node):
        return {
            'name'       : node['name'], 'display_name': node.get('display_name', ''),
            'addr'       : node['addr'], 'port': node['port'], 'uuid': node['uuid'],
            'incarnation': node['incarnation'], 'groups': node.get('groups', []),
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
        # Node messages are before all others
        b = {'send': 0, 'msg': msg, 'prioritary': True}
        broadcaster.append(b)
        # Also send it to the websocket if there
        self.forward_to_websocket(msg)
        return
    
    
    def stack_event_broadcast(self, payload):
        msg = self.create_event_msg(payload)
        b = {'send': 0, 'msg': msg}
        broadcaster.append(b)
        return
    
    
    def stack_new_ts_broadcast(self, key):
        msg = self.create_new_ts_msg(key)
        b = {'send': 0, 'msg': msg, 'groups': 'ts'}
        broadcaster.append(b)
        return
    
    
    def stack_suspect_broadcast(self, node):
        msg = self.create_suspect_msg(node)
        # Node messages are before all others
        b = {'send': 0, 'msg': msg, 'prioritary': True}
        broadcaster.append(b)
        # Also send it to the websocket if there
        self.forward_to_websocket(msg)
        return b
    
    
    def stack_leave_broadcast(self, node):
        msg = self.create_leave_msg(node)
        # Node messages are before all others
        b = {'send': 0, 'msg': msg, 'prioritary': True}
        broadcaster.append(b)
        # Also send it to the websocket if there
        self.forward_to_websocket(msg)
        return b
    
    
    def stack_dead_broadcast(self, node):
        msg = self.create_dead_msg(node)
        # Node messages are before all others
        b = {'send': 0, 'msg': msg, 'prioritary': True}
        broadcaster.append(b)
        self.forward_to_websocket(msg)
        return b
    
    
    def forward_to_websocket(self, msg):
        websocketmgr.forward({'channel': 'gossip', 'payload': msg})
    
    
    ############## Http interface
    # We must create http callbacks in running because
    # we must have the self object
    def export_http(self):
        
        @http_export('/agent/name')
        def get_name():
            return self.nodes[self.uuid]['name']
        
        
        @http_export('/agent/uuid')
        def get_name():
            return self.uuid
        
        
        @http_export('/agent/leave/:nuuid')
        def set_node_leave(nuuid):
            node = None
            with self.nodes_lock:
                node = self.nodes.get(nuuid, None)
            if node is None:
                return abort(404, 'This node is not found')
            self.set_leave(node)
            return
        
        
        @http_export('/agent/members')
        def agent_members():
            response.content_type = 'application/json'
            with self.nodes_lock:
                nodes = copy.copy(self.nodes)
            return nodes
        
        
        @http_export('/agent/members/history', method='GET')
        def agent_members_history():
            response.content_type = 'application/json'
            r = gossiper.get_history()
            return json.dumps(r)
        
        
        @http_export('/agent/join/:other')
        def agent_join(other):
            response.content_type = 'application/json'
            addr = other
            port = self.port
            if ':' in other:
                parts = other.split(':', 1)
                addr = parts[0]
                port = int(parts[1])
            tgt = (addr, port)
            r = self.do_push_pull(tgt)
            return json.dumps(r)
        
        
        @http_export('/agent/push-pull')
        def interface_push_pull():
            response.content_type = 'application/json'
            
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
            
            return json.dumps(m)
        
        
        @http_export('/agent/detect')
        def agent_members():
            response.content_type = 'application/json'
            nodes = self.launch_gossip_detect_ping()
            return json.dumps(nodes)
        
        
        # Add a group should only be allowed by unix socket (local)
        @http_export('/agent/parameters/add/groups/:gname', protected=True)
        def agent_add_group(gname):
            response.content_type = 'application/json'
            r = self.add_group(gname)
            return json.dumps(r)
        
        
        # Add a group should only be allowed by unix socket (local)
        @http_export('/agent/parameters/remove/groups/:gname', protected=True)
        def agent_remove_group(gname):
            response.content_type = 'application/json'
            r = self.remove_group(gname)
            return json.dumps(r)
        
        
        @http_export('/agent/zones', method='GET', protected=True)
        def get_zones():
            response.content_type = 'application/json'
            return json.dumps(zonemgr.get_zones())
        
        
        @http_export('/agent/event/:event_type', method='GET', protected=True)
        def get_event(event_type):
            response.content_type = 'application/json'
            evt = None
            with self.events_lock:
                for (cid, e) in self.events.iteritems():
                    if e.get('type') == event_type:
                        evt = e
            return json.dumps(evt)


gossiper = Gossip()
