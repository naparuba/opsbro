import socket
import os
import time
import random
import math
import copy
import bisect
import threading
from collections import deque
import traceback
import shutil
from contextlib import closing as closing_context

# some singleton :)
from .log import LoggerFactory
from .threadmgr import threader
from .broadcast import broadcaster
from .websocketmanager import websocketmgr
from .pubsub import pubsub
from .library import libstore
from .httpclient import get_http_exceptions, httper
from .stop import stopper
from .handlermgr import handlermgr
from .topic import topiker, TOPIC_SERVICE_DISCOVERY
from .basemanager import BaseManager
from .jsonmgr import jsoner
from .util import get_uuid
from .udprouter import udprouter
from .zonemanager import zonemgr

_64K = 65535

KGOSSIP = 10

# LIMIT= 4 * math.ceil(math.log10(float(2 + 1)))

# Global logger for this part
logger = LoggerFactory.create_logger('gossip')


class NODE_STATES(object):
    ALIVE = 'alive'
    DEAD = 'dead'
    LEAVE = 'leave'
    SUSPECT = 'suspect'
    UNKNOWN = 'unknown'


class PACKET_TYPES(object):
    # ping and co
    PING = 'gossip::ping'
    PING_RELAY = 'gossip::ping-relay'
    DETECT_PING = 'gossip::detect-ping'
    DETECT_PONG = 'gossip::detect-pong'
    ACK = 'gossip::ack'
    
    # with states
    ALIVE = 'gossip::alive'
    SUSPECT = 'gossip::suspect'
    DEAD = 'gossip::dead'
    LEAVE = 'gossip::leave'


# Main class for a Gossip cluster
class Gossip(BaseManager):
    history_directory_suffix = 'nodes'
    
    
    def __init__(self):
        super(Gossip, self).__init__()
        self.logger = logger
        # Set myself as master of the gossip:: udp messages
        udprouter.declare_handler('gossip', self)
        # We must protect the nodes with a lock
        self.nodes_lock = threading.RLock()
    
    
    def init(self, nodes_file, local_addr, public_addr, port, name, display_name, incarnation, uuid, groups, seeds, bootstrap, zone, is_proxy):
        self.uuid = uuid
        self._nodes_file = nodes_file
        self.local_addr = local_addr
        self.public_addr = public_addr
        self.port = port
        self.name = name
        self.display_name = display_name
        self.incarnation = incarnation
        
        self.groups = groups  # finally computed groups
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
        self.max_event_age = 300
        
        self._load_nodes()
        self.__refresh_read_only_nodes()  # Create the self.nodes
        
        # We update our nodes list based on our current zone. We keep our zone, only proxy from top zone
        # and all the sub zones
        self.clean_nodes_from_zone()
        
        # export my http uri now I got a real self
        self.export_http()
        
        # When something change, we save it in the history
        self.prepare_history_directory()  # the configmgr is ready at this state
        
        # create my own object, but do not export it to other nodes
        self.__register_myself()
    
    
    def __getitem__(self, uuid):
        return self.nodes[uuid]
    
    
    def save_retention(self):
        with open(self._nodes_file + '.tmp', 'w') as f:
            with self.nodes_lock:
                nodes = copy.copy(self.nodes)
            f.write(jsoner.dumps(nodes))
        # now more the tmp file into the real one
        shutil.move(self._nodes_file + '.tmp', self._nodes_file)
    
    
    def _load_nodes(self):
        # Now load nodes to do not start from zero, but not ourselves (we will regenerate it with a new incarnation number and
        # up to date info)
        nodes = {}
        if self._nodes_file and os.path.exists(self._nodes_file):
            with open(self._nodes_file, 'r') as f:
                nodes = jsoner.loads(f.read())
                # If we were in nodes, remove it, we will refresh it
                if self.uuid in nodes:
                    del nodes[self.uuid]
        # Beware about old retention files, previous to 0.5 that do not have local/public address
        for node in nodes:
            public_addr = node.get('public_addr', None)
            if public_addr is None:
                node['public_addr'] = node['addr']
                node['local_addr'] = node['addr']
                del node['addr']
        
        # For each nodes we must compute the addr from our point of view
        for node in nodes:
            self._compute_node_address(node)
        
        self._nodes_writing = nodes
    
    
    # each second we look for all old events in order to clean and delete them :)
    def __clean_old_events(self):
        now = int(time.time())
        to_del = []
        with self.events_lock:
            for (cid, e) in self.events.items():
                ctime = e.get('ctime', 0)
                if ctime < now - self.max_event_age:
                    to_del.append(cid)
            
            for cid in to_del:
                try:
                    del self.events[cid]
                except IndexError:  # if already delete, we don't care
                    pass
    
    
    def have_event_type(self, event_type):
        with self.events_lock:
            for e in self.events.values():
                e_type = e.get('payload', {}).get('type', None)
                if e_type == event_type:
                    return True
        return False
    
    
    def add_event(self, event):
        logger.info('ADD NEW EVENT %s' % event)
        eventid = event.get('eventid', None)
        if eventid is None:
            return
        with self.events_lock:
            self.events[eventid] = event
    
    
    # We cant nodes that are not officially off, so not down, leave, but suspect is ok
    def get_uuids_of_my_zone_not_off_nodes(self):
        return [node['uuid'] for node in self.nodes.values() if node['zone'] == self.zone and node['state'] in [NODE_STATES.ALIVE, NODE_STATES.SUSPECT]]
    
    
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
            for (nuuid, node) in self.nodes.items():
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
                # Other zone, or unknown
                else:
                    to_del.append(nuuid)
            if len(to_del) > 0:
                logger.info("We have %d dirty nodes to remove because their zone is not valid from our own zone (%s)" % (len(to_del), self.zone))
                for nuuid in to_del:
                    node = self._nodes_writing[nuuid]
                    logger.info('CLEANING we are in zone %s so we are removing a node from a unmanaged/distant zone: %s/%s (was in zone %s)' % (self.zone, nuuid, node['name'], node['zone']))
                # We can clean them now, in bulk mode (so we only regenerate read only nodes once)
                self.delete_nodes(to_del)
    
    
    def get(self, uuid, default=None):
        return self.nodes.get(uuid, default)
    
    
    def __iter__(self):
        return self.nodes.__iter__()
    
    
    def __contains__(self, uuid):
        return uuid in self.nodes
    
    
    # Inserting a new node
    def __setitem__(self, uuid, new_node):
        with self.nodes_lock:
            self._nodes_writing[uuid] = new_node
            self.__refresh_read_only_nodes()
    
    
    def __delitem__(self, node_uuid):
        with self.nodes_lock:
            if node_uuid not in self._nodes_writing:
                return
            del self._nodes_writing[node_uuid]
            self.__refresh_read_only_nodes()
    
    
    # We did change nodes so we are updating the read only copy with the new nodes DICT
    # WE DO NOT COPY nodes themselve, so YOU MUST respect and don't edit them! (or atomic write only)
    def __refresh_read_only_nodes(self):
        with self.nodes_lock:
            nodes_copy = copy.copy(self._nodes_writing)
            self.nodes = nodes_copy
    
    
    def __register_myself(self):
        myself = self.__get_boostrap_node()
        self.set_alive(myself, bootstrap=True)
    
    
    def is_in_group(self, group):
        return group in self.groups
    
    
    def __add_group_change_history_entry(self, group, action):
        node = self._get_myself_read_only()
        history_entry = {'type': 'group-%s' % action,
                         'name': node['name'], 'display_name': node.get('display_name', ''),
                         'uuid': node['uuid'], 'group': group,
                         }
        
        self.add_history_entry(history_entry)
    
    
    def __add_node_state_change_history_entry(self, node, old_state, new_state):
        history_entry = {'type': 'node-state-change',
                         'name': node['name'], 'display_name': node.get('display_name', ''),
                         'uuid': node['uuid'], 'old_state': old_state, 'state': new_state,
                         }
        logger.debug('__add_node_state_change_history_entry:: %s' % history_entry)
        self.add_history_entry(history_entry)
    
    
    def __add_node_zone_change_history_entry(self, node, old_zone, new_zone):
        history_entry = {'type': 'node-zone-change',
                         'name': node['name'], 'display_name': node.get('display_name', ''),
                         'uuid': node['uuid'], 'old_zone': old_zone, 'zone': new_zone,
                         }
        logger.debug('__add_node_zone_change_history_entry:: %s' % history_entry)
        self.add_history_entry(history_entry)
    
    
    # Each seconds we try to save a history entry (about add/remove groups, or new nodes)
    def do_history_save_loop(self):
        while not stopper.is_stop():
            self.write_history_entry()
            time.sleep(1)
    
    
    def add_group(self, group, broadcast_when_change=True):
        with self.nodes_lock:
            # if group already in exit with False (don't changed)
            if group in self.groups:
                return False
            
            new_groups = copy.copy(self.groups)
            new_groups.append(group)
            self.groups = new_groups
            self._set_myself_atomic_property('groups', self.groups)
            
            logger.info('The group %s was added.' % group)
            # If our groups did change and we did allow to broadcast here (like in CLI call but not in
            # auto discovery because we want to send only 1 network packet), we can broadcast it
            # We always stack a history entry, it's only save once a seconds
            self.__add_group_change_history_entry(group, 'add')
            # Let the handlers known about it
            handlermgr.launch_group_handlers(group, 'add')
            # but not always network, must be done once a loop
            if broadcast_when_change:
                self.node_did_change(self.uuid)  # a node did change: ourselve
                self.increase_incarnation_and_broadcast()
        
        return True  # we did change
    
    
    def remove_group(self, group, broadcast_when_change=True):
        with self.nodes_lock:
            if group not in self.groups:
                return False
            new_groups = copy.copy(self.groups)
            new_groups.remove(group)
            self.groups = new_groups
            self._set_myself_atomic_property('groups', self.groups)
            # let the caller known that we did work
            logger.info('The group %s was removed.' % group)
            
            # If our groups did change and we did allow to broadcast here (like in CLI call but not in
            # auto discovery because we want to send only 1 network packet), we can broadcast it
            # We always stack a history entry, it's only save once a seconds
            self.__add_group_change_history_entry(group, 'remove')
            # Let the handlers known about it
            handlermgr.launch_group_handlers(group, 'remove')
            
            # but not always network, must be done once a loop
            if broadcast_when_change:
                self.node_did_change(self.uuid)  # a node did change: ourselve
                self.increase_incarnation_and_broadcast()
        return True  # we did change
    
    
    # find all nearly alive nodes with a specific group
    def find_group_nodes(self, group):
        nodes = []
        for (uuid, node) in self.nodes.items():
            if node['state'] in [NODE_STATES.DEAD, NODE_STATES.LEAVE]:
                continue
            groups = node.get('groups', [])
            if group in groups:
                nodes.append(uuid)
        return nodes
    
    
    # find all nearly alive nodes with a specific name or display_name
    def find_nodes_by_name_or_display_name(self, name):
        nodes = []
        for (uuid, node) in self.nodes.items():
            if node['state'] in [NODE_STATES.DEAD, NODE_STATES.LEAVE]:
                continue
            if name == node.get('name') or name == node.get('display_name'):
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
        nuuid = group_nodes[idx]
        return nuuid
    
    
    def count(self, state='', group=''):
        if group:
            if state:
                return len([n for n in self.nodes.values() if group in n['groups'] and n['state'] == state])
            else:  # no filter, take all
                return len([n for n in self.nodes.values() if group in n['groups']])
        else:
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
                # We do not want to send a broadcast now, we have still other group to manage
                # and send only one change
                self.add_group(group, broadcast_when_change=False)
                logger.debug("New group detected from detector for this node: %s" % group)
        for group in deleted_groups:
            if self.is_in_group(group):
                did_change = True
                # We do not want to send a broadcast now, we have still other group to manage
                # and send only one change
                self.remove_group(group, broadcast_when_change=False)
                logger.debug("Group was lost from the previous detection for this node: %s" % group)
        # warn other parts only if need, and do it only once even for lot of groups
        if did_change:
            self.node_did_change(self.uuid)  # a node did change: ourselve
            self.increase_incarnation_and_broadcast()
        
        return did_change
    
    
    def _get_myself_read_only(self):
        return self.nodes[self.uuid]
    
    
    def _get_myself_write_allowed(self):
        return self._nodes_writing[self.uuid]
    
    
    # We are updating a property of myself, so we must do in both read only and
    # write allowed myself node
    def _set_myself_atomic_property(self, prop, value):
        with self.nodes_lock:
            myself_read_only = self._get_myself_read_only()
            myself_read_only[prop] = value
            
            myself_write_allowed = self._get_myself_write_allowed()
            myself_write_allowed[prop] = value
            
            if myself_read_only is not myself_write_allowed:
                raise Exception('Oups, both objects are differents')
            if id(myself_read_only) != id(myself_write_allowed):
                raise Exception('Oups, both objects ids are differents')
    
    
    # A check did change it's state (we did check this), update it in our structure
    # but beware: in an ATOMIC way from the node poitn of view
    def update_check_state_id(self, cname, state_id):
        with self.nodes_lock:
            myself = self._get_myself_write_allowed()
            check_entry = myself['checks'].get(cname, None)
            # We can just atomic write it
            if check_entry is not None:
                check_entry['state_id'] = state_id
                return
            # ok need to update the full checks structure, and in an atomic way, so need to clone it first
            new_checks = copy.deepcopy(myself['checks'])
            new_checks[cname] = {'state_id': state_id}
            myself['checks'] = new_checks
    
    
    # We did have a massive change or a bad information from network, we must
    # fix this and warn others about good information
    def increase_incarnation_and_broadcast(self):
        self.incarnation += 1
        # As it's a simple operation, just update both nodes read only, and write one
        self._set_myself_atomic_property('incarnation', self.incarnation)
        myself_read_only = self._get_myself_read_only()
        
        my_state = myself_read_only['state']
        if my_state == NODE_STATES.ALIVE:
            self.stack_alive_broadcast(myself_read_only)
        elif my_state == NODE_STATES.LEAVE:
            self.stack_leave_broadcast(myself_read_only)
        else:
            raise Exception('Asking for an unknown broadcast type for node: %s => %s' % (myself_read_only, my_state))
        logger.info('Did have to send a new incarnation node for myself. New incarnation=%d new-node=%s' % (self.incarnation, myself_read_only))
    
    
    def change_zone(self, zname):
        if self.zone == zname:
            return
        logger.info('Switching to zone: %s' % zname)
        if not zonemgr.have_zone(zname):
            raise ValueError('No such zone')
        self.zone = zname
        # Simple string change, we can change both write and read node
        self._set_myself_atomic_property('zone', zname)
        # let the others nodes know it
        self.increase_incarnation_and_broadcast()
        # As we did change, we need to update our own node list to keep only what we should
        self.clean_nodes_from_zone()
    
    
    def get_zone_from_node(self, node_uuid=''):
        if not node_uuid:
            node_uuid = self.uuid
        node = self.nodes.get(node_uuid, None)
        if node is None:
            return ''
        node_zone = node.get('zone', '')
        logger.debug('get_zone_from_node:: giving back %s' % node_zone)
        return node_zone
    
    
    def get_number_of_nodes(self):
        return len(self.nodes)
    
    
    # get my own node entry
    def __get_boostrap_node(self):
        node = {'public_addr': self.public_addr, 'local_addr': self.local_addr,
                'port'       : self.port, 'name': self.name, 'display_name': self.display_name,
                'incarnation': self.incarnation, 'uuid': self.uuid, 'state': NODE_STATES.ALIVE, 'groups': self.groups,
                'services'   : {}, 'checks': {}, 'zone': self.zone, 'is_proxy': self.is_proxy}
        return node
    
    
    # Definitivly remove a node from our list, and warn others about it
    def delete_node(self, nid):
        if nid not in self.nodes:
            return
        with self.nodes_lock:
            del self._nodes_writing[nid]
            self.__refresh_read_only_nodes()
        
        # Le the modules know about it
        pubsub.pub('delete-node', node_uuid=nid)
    
    
    def delete_nodes(self, nodes_uuids):
        with self.nodes_lock:
            did_delete = False
            for node_uuid in nodes_uuids:
                if node_uuid not in self._nodes_writing:
                    continue
                did_delete = True
                del self._nodes_writing[node_uuid]
                
                # Let the modules know about it
                pubsub.pub('delete-node', node_uuid=node_uuid)
            # We did delete some nodes, so refresh the read only nodes list
            if did_delete:
                self.__refresh_read_only_nodes()
    
    
    # For a node we store the address we should communicate with:
    # * same zone: local address
    # * other zone: public address only
    def _compute_node_address(self, node):
        node_zone = node['zone']
        if node_zone != self.zone:
            node['addr'] = node['public_addr']
        else:
            node['addr'] = node['local_addr']
    
    
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
        
        # we should compute the addr we should consider for this node
        # from our point of view
        self._compute_node_address(node)
        
        # Add the node but in a protected mode
        with self.nodes_lock:
            self._nodes_writing[nuuid] = node
            self.__refresh_read_only_nodes()
        
        # if bootstrap, do not export to other nodes or modules
        if bootstrap:
            return
        
        # Save this change into our history
        self.__add_node_state_change_history_entry(node, NODE_STATES.UNKNOWN, node['state'])
        
        # Warn network elements
        self.stack_alive_broadcast(node)
        # And finally callback other part of the code about this
        pubsub.pub('new-node', node_uuid=nuuid)
        return
    
    
    # Warn other about a node that is not new or remove, but just did change it's internals data
    @staticmethod
    def node_did_change(nid):
        pubsub.pub('change-node', node_uuid=nid)
    
    
    ############# Main new state handling methods
    
    # Set alive a node we eart about. 
    # * It can be us if we allow the bootstrap node (only at startup).
    # * If strong it means we did the check, so we believe us :)
    def set_alive(self, node, bootstrap=False, strong=False):
        name = node['name']
        incarnation = node['incarnation']
        uuid = node['uuid']
        state = node['state'] = NODE_STATES.ALIVE
        
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
                    self.increase_incarnation_and_broadcast()
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
                self._nodes_writing[uuid] = node
                self.__refresh_read_only_nodes()
            
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
        state = NODE_STATES.SUSPECT
        
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
        if prev_state != NODE_STATES.ALIVE:
            return
        
        # Maybe it's us?? We need to say FUCKING NO, I'm alive!! (or maybe leave, but not a suspect)
        if uuid == self.uuid:
            myself = node
            my_state = myself['state']
            logger.warning('SUSPECT: SOMEONE THINK I AM SUSPECT, BUT I AM %s' % my_state)
            # Is we are leaving, let the other know we are not a suspect, but a leaving node
            self.increase_incarnation_and_broadcast()
            return
        
        logger.info('SUSPECTING: I suspect node %s' % node['name'])
        # Ok it's definitivly someone else that is now suspected, update this, and update it :)
        # We can update both write & read node
        now = int(time.time())
        
        node['incarnation'] = incarnation
        node['state'] = state
        node['suspect_time'] = now
        
        # warn internal elements
        self.node_did_change(uuid)
        # Save this change into our history
        self.__add_node_state_change_history_entry(node, prev_state, node['state'])
        # and external ones
        self.stack_suspect_broadcast(node)
    
    
    # Define a function that will wait 10s to let the others nodes know that we did leave
    # and then ask for a clean stop of the daemon
    @staticmethod
    def _bailout_after_leave():
        wait_time = 10
        logger.info('Waiting out %s seconds before exiting as we are set in leave state' % wait_time)
        time.sleep(10)
        logger.info('Exiting from a self leave message')
        # Will set self.interrupted = True to every thread that loop
        stopper.do_stop('Exiting from a leave massage')
    
    
    # Someone ask us about a leave node, so believe it
    # Leave node are about all states, so we don't filter by current state
    # if the incarnation is ok, we believe it
    # FORCE: if True, means we can believe it, it's not from gossip, but from
    #        a protected HTTP call
    def set_leave(self, leaved, force=False):
        incarnation = leaved['incarnation']
        uuid = leaved['uuid']
        state = NODE_STATES.LEAVE
        
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
        if prev_state == NODE_STATES.LEAVE:
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
        
        # Maybe it's us, but from a untrusted source (gossip), if so fix it on the gossip network
        if uuid == self.uuid:
            if not force:
                # Ok it's really our own incarnation, we must fix it
                if incarnation == node['incarnation']:
                    self.increase_incarnation_and_broadcast()
                return
            # Ok the CLI or HTTP protected call ask us to be in leave mode
            else:
                
                logger.info('LEAVE: someone is asking me for leaving.')
                # Mark myself as leave so
                self._set_myself_atomic_property('state', state)
                self.increase_incarnation_and_broadcast()
                
                threader.create_and_launch(self._bailout_after_leave, name='Exiting agent after set to leave', part='agent')
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
        state = NODE_STATES.DEAD
        
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
        if prev_state != NODE_STATES.ALIVE:
            return
        
        # Maybe it's us?? We need to say FUCKING NO, I'm alive!!
        if uuid == self.uuid:
            logger.warning('DEAD: SOMEONE THINK I AM DEAD, BUT I AM ALIVE')
            self.increase_incarnation_and_broadcast()
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
    # but we will drop the one we should not see (like if a top node
    # send nodes it should not)
    def merge_nodes(self, nodes):
        for (k, node) in nodes.items():
            # Maybe it's me? bail out
            if node['uuid'] == self.uuid:
                logger.debug('SKIPPING myself node entry in merge nodes')
                continue
            
            logger.info('SOMEONE GIVE A NODE: %s' % node)
            node_zone = node.get('zone', None)
            if node_zone is None:
                continue
            if node_zone != self.zone:
                # sub zone are accepted, but top zone should be only one
                # level high, not too much (should not have this)
                if zonemgr.is_top_zone_from(self.zone, node_zone):
                    if not zonemgr.is_direct_sub_zone_from(node_zone, self.zone):  # too high
                        logger.debug('SKIPPING node because it is from a too high zone: %s' % node_zone)
                        continue
            state = node['state']
            
            # Try to incorporate it
            if state == NODE_STATES.ALIVE:
                self.set_alive(node)
            # note: for dead, we never believe others for dead, we set suspect
            # and wait for timeout to finish
            elif state == NODE_STATES.DEAD or state == NODE_STATES.SUSPECT:
                self.set_suspect(node)
            elif state == NODE_STATES.LEAVE:
                self.set_leave(node)
    
    
    def merge_events(self, events):
        with self.events_lock:
            for (eventid, event) in events.items():
                logger.debug('Try to merge event', eventid, event)
                payload = event.get('payload', {})
                # if bad event or already known one, delete it
                if not eventid or not payload or eventid in self.events:
                    continue
                # ok new one, add a broadcast so we diffuse it, and manage it
                b = {'send': 0, 'msg': event}
                broadcaster.append(b)
                
                # Remember this event to not spam it
                logger.info('DID MERGE EVENT from another node: %s' % event)
                self.add_event(event)
    
    
    # We cannot full sync with all nodes:
    # * must be alive
    # * not ourselve ^^
    # * all of our own zone
    # * top zone: only proxy node
    # * lower zone: NO: we don't initialize sync to lower zone, they will do it themselve
    def __get_valid_nodes_to_full_sync(self):
        nodes = self.nodes
        top_zones = zonemgr.get_top_zones_from(self.zone)
        
        possible_nodes = []
        for n in nodes.values():
            # skip ourselve
            if n['uuid'] == self.uuid:
                continue
            # skip bad nodes, must be alive
            if n['state'] != NODE_STATES.ALIVE:
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
            possible_nodes.append((n['public_addr'], n['port']))
        return possible_nodes
    
    
    # We will choose a random guy in our nodes that is alive, and
    # sync with it
    def launch_full_sync_loop(self):
        while not stopper.is_stop():
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
        while not stopper.is_stop():
            if topiker.is_topic_enabled(TOPIC_SERVICE_DISCOVERY):
                self.launch_gossip()
            self.__clean_old_events()
            time.sleep(1)
    
    
    def launch_gossip(self):
        # There is no broadcast message to sent so bail out :)
        if len(broadcaster.broadcasts) == 0:
            return
        
        nodes = self.nodes
        
        # First we need to send all message to the others TOP zone, and do not 'consume' messages
        # only our zone will consume them so we are sure they will disapear
        if self.is_proxy:
            top_zones = zonemgr.get_top_zones_from(self.zone)
            for zname in top_zones:
                # we don't care about leave node, but we need others to be proxy
                others = [n for n in nodes.values() if n['zone'] == zname and n['state'] != NODE_STATES.LEAVE and n['is_proxy'] is True]
                # Maybe there is no valid nodes for this zone, skip it
                if len(others) == 0:
                    continue
                # Limit the broadcast
                nb_dest = min(len(others), KGOSSIP)
                dests = random.sample(others, nb_dest)
                for dest in dests:
                    logger.info("launch_gossip:: topzone::%s  to node::%s" % (zname, dest['name']))
                    self.__do_gossip_push(dest, consume=False)
        
        # always send to our zone, but not for leave nodes
        others = [n for n in nodes.values() if n['uuid'] != self.uuid and n['zone'] == self.zone and n['state'] != NODE_STATES.LEAVE]
        logger.debug("launch_gossip:: our zone nodes %d" % len(others))
        
        # Maybe every one is dead, if o bail out
        if len(others) == 0:
            return
        nb_dest = min(len(others), KGOSSIP)
        dests = random.sample(others, nb_dest)
        for dest in dests:
            logger.debug("launch_gossip::  into own zone::%s  to %s(%s)" % (self.zone, dest['name'], dest['display_name']))
            self.__do_gossip_push(dest, consume=True)
    
    
    # We cannot ping with all nodes:
    # * must be not leave, we can ping dead/suspect, to check if they are still not OK
    # * not ourselve ^^
    # * all of our own zone
    # * top zone: only proxy node and if we are a proxy node
    # * lower zone: only proxy node and if we are a proxy node
    def __get_valid_nodes_to_ping(self):
        nodes = self.nodes
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
            if n['state'] == NODE_STATES.LEAVE:
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
        while not stopper.is_stop():
            if topiker.is_topic_enabled(TOPIC_SERVICE_DISCOVERY):
                self.ping_another()
            time.sleep(1)
    
    
    # we ping some K random nodes, but in priority some nodes that we thouugh were deads
    # but talk to us
    # also exclude leave node, because thay said they are not here anymore ^^
    def ping_another(self):
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
    
    
    # Launch a ping to another node and if fail set it as suspect
    def __do_ping(self, other):
        addr = other['public_addr']
        port = other['port']
        other_zone_name = other['zone']
        ping_zone = other_zone_name
        # If the other node is a top level one, we must use our own zone, because we don't have it's
        if zonemgr.is_top_zone_from(self.zone, other_zone_name):
            ping_zone = self.zone
        ping_payload = {'type': PACKET_TYPES.PING, 'seqno': 0, 'node': other['uuid'], 'from_zone': self.zone, 'from': self.uuid}
        message = jsoner.dumps(ping_payload)
        encrypter = libstore.get_encrypter()
        enc_message = encrypter.encrypt(message, dest_zone_name=ping_zone)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            sock.sendto(enc_message, (addr, port))
            logger.debug('PING waiting %s ack message' % other['name'])
            # Allow 3s to get an answer
            sock.settimeout(3)
            ret = sock.recv(_64K)
            uncrypted_ret = encrypter.decrypt(ret)
            logger.debug('RECEIVING PING RESPONSE: %s' % uncrypted_ret)
            try:
                msg = jsoner.loads(uncrypted_ret)
                new_other = msg['node']
                logger.debug('PING got a return from %s (%s) (node state)=%s: %s' % (new_other['name'], new_other['display_name'], new_other['state'], msg))
                if new_other['state'] == NODE_STATES.ALIVE:
                    # An aswer? great it is alive!
                    self.set_alive(other, strong=True)
                elif new_other['state'] == NODE_STATES.LEAVE:
                    self.set_leave(new_other)
                else:
                    logger.error('PING the other node %s did give us a unamanged state: %s' % (new_other['name'], new_other['state']))
                    self.set_suspect(new_other)
            except ValueError:  # bad json
                self.set_suspect(other)
        except (socket.timeout, socket.gaierror) as exp:
            logger.info("PING: error joining the other node %s:%s : %s. Switching to a indirect ping mode." % (addr, port, exp))
            possible_relays = [n for n in self.nodes.values() if
                               n['uuid'] != self.uuid
                               and n != other
                               and n['zone'] == other_zone_name
                               and n['state'] == NODE_STATES.ALIVE
                               ]
            
            if len(possible_relays) == 0:
                logger.info("PING: no possible relays for ping")
                self.set_suspect(other)
            # Take at least 3 relays to ask ping
            relays = random.sample(possible_relays, min(len(possible_relays), 3))
            logger.debug('POSSIBLE RELAYS', relays)
            ping_relay_payload = {'type': PACKET_TYPES.PING_RELAY, 'seqno': 0, 'tgt': other['uuid'], 'from': self.uuid, 'from_zone': self.zone}
            message = jsoner.dumps(ping_relay_payload)
            enc_message = encrypter.encrypt(message, dest_zone_name=ping_zone)  # relays are all in the other zone, so same as before
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            for r in relays:
                try:
                    sock.sendto(enc_message, (r['public_addr'], r['port']))
                    logger.info('PING waiting ack message from relay %s about node %s' % (r['display_name'], other['display_name']))
                except socket.error as exp:
                    logger.error('Cannot send a ping relay to %s:%s' % (r['public_addr'], r['port']))
            # Allow 3s to get an answer from whatever relays got it
            sock.settimeout(3 * 2)
            try:
                ret = sock.recv(_64K)
            except socket.timeout:
                logger.info('PING RELAY: no response from relays about node %s' % other['display_name'])
                # still noone succed to ping it? I suspect it
                self.set_suspect(other)
                sock.close()
                return
            sock.close()
            uncrypted_ret = encrypter.decrypt(ret)
            msg = jsoner.loads(uncrypted_ret)
            new_other = msg['node']
            logger.debug('PING got a return from %s (%s) via a relay: %s' % (new_other['name'], new_other['display_name'], msg))
            # Ok it's no more suspected, great :)
            if new_other['state'] == NODE_STATES.ALIVE:
                # An aswer? great it is alive!
                self.set_alive(other, strong=True)
            elif new_other['state'] == NODE_STATES.LEAVE:
                self.set_leave(new_other)
            else:
                logger.error('PING the other node %s did give us a unamanged state: %s' % (new_other['name'], new_other['state']))
                self.set_suspect(new_other)
        except socket.error as exp:
            logger.info("PING: cannot join the other node %s:%s : %s" % (addr, port, exp))
    
    
    def manage_ping_message(self, m, addr):
        # if it me that the other is pinging? because it can think to
        # thing another but in my addr, like it I did change my name
        did_want_to_ping_uuid = m.get('node', None)
        if did_want_to_ping_uuid != self.uuid:  # not me? skip this
            logger.info('A node ask us a ping but it is not for our uuid, skiping it')
            return
        from_zone = m.get('from_zone', None)
        if from_zone is None:  # malformed ping message
            return
        # Maybe the caller is from a top zone level. If so, we don't have it's zone, so
        # use our own
        ack_zone_to_use = from_zone
        if zonemgr.is_top_zone_from(self.zone, from_zone):
            ack_zone_to_use = self.zone
        
        my_self = self._get_myself_read_only()
        my_node_data = self.create_alive_msg(my_self)
        ack = {'type': PACKET_TYPES.ACK, 'seqno': m['seqno'], 'node': my_node_data}
        ret_msg = jsoner.dumps(ack)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        encrypter = libstore.get_encrypter()
        enc_ret_msg = encrypter.encrypt(ret_msg, dest_zone_name=ack_zone_to_use)
        sock.sendto(enc_ret_msg, addr)
        sock.close()
        logger.debug("PING RETURN ACK MESSAGE", ret_msg)
        
        # now maybe the source was a suspect that just ping me? if so
        # ask for a future ping
        fr_uuid = m['from']
        node = self.get(fr_uuid)
        if node and node['state'] != NODE_STATES.ALIVE:
            logger.debug('PINGBACK +ing node', node['name'])
            self.to_ping_back.append(fr_uuid)
    
    
    def send_raft_message(self, dest_uuid, message):
        self.send_message_to_other(dest_uuid, message)  # raft is just a standard message
    
    
    # We are ask to do a indirect ping to tgt and return the ack to
    # _from, do this in a thread so we don't lock here
    def do_indirect_ping(self, tgt, _from, addr):
        logger.info('do_indirect_ping', tgt, _from)
        ntgt = self.get(tgt, None)
        nfrom = self.get(_from, None)
        # If the dest or the from node are now unknown, exit this thread
        if not ntgt or not nfrom:
            logger.info('PING: asking for a ping relay for a node I dont know about: about %s from %s' % (ntgt, nfrom))
            return
        tgtaddr = ntgt['public_addr']
        tgtport = ntgt['port']
        tgt_zone = ntgt['zone']
        # Maybe the target zone is too high, if so we don't have it's key, so use our own
        if zonemgr.is_top_zone_from(self.zone, tgt_zone):
            tgt_zone = self.zone
        # Now do the real ping
        ping_payload = {'type': PACKET_TYPES.PING, 'seqno': 0, 'node': ntgt['uuid'], 'from': self.uuid}
        message = jsoner.dumps(ping_payload)
        encrypter = libstore.get_encrypter()
        enc_message = encrypter.encrypt(message, dest_zone_name=tgt_zone)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            sock.sendto(enc_message, (tgtaddr, tgtport))
            logger.debug('PING waiting %s ack message from a ping-relay' % ntgt['display_name'])
            # Allow 3s to get an answer
            sock.settimeout(3)
            ret = sock.recv(65535)
            uncrypted_ret = encrypter.decrypt(ret)
            j_ret = jsoner.loads(uncrypted_ret)
            logger.info('PING (relay) got a return from %s' % ntgt['name'], j_ret)
            # An aswer? great it is alive! Let it know our _from node
            ack = {'type': PACKET_TYPES.ACK, 'seqno': 0, 'node': j_ret['node']}
            ret_msg = jsoner.dumps(ack)
            nfrom_zone = nfrom['zone']
            # Same as before: cannot talk to higher zone
            if zonemgr.is_top_zone_from(self.zone, nfrom_zone):
                nfrom_zone = self.zone
            enc_ret_msg = encrypter.encrypt(ret_msg, dest_zone_name=nfrom_zone)
            sock.sendto(enc_ret_msg, addr)
            sock.close()
        except (socket.timeout, socket.gaierror) as exp:
            # cannot reach even us? so it's really dead, let the timeout do its job on _from
            logger.info('PING (relay): cannot ping the node %s(%s:%s) for %s: %s' % (ntgt['display_name'], tgtaddr, tgtport, nfrom['display_name'], exp))
        except Exception as exp:
            logger.error('PING (relay) error, cannot ping-relay for a node: %s' % exp)
    
    
    def manage_ping_relay_message(self, m, addr):
        tgt = m.get('tgt')
        _from = m.get('from', '')
        if not tgt or not _from:
            return
        
        # Do the indirect ping as a sub-thread
        threader.create_and_launch(self.do_indirect_ping, name='indirect-ping-%s-%s' % (tgt, _from), args=(tgt, _from, addr), part='gossip')
    
    
    # A node did send us a discovery message but with the valid network key of course.
    # If so, give back our node informations:
    # * if same zone or top zone: give our informations
    # * if directly lower zone: give us only if we are a proxy
    # * lower 2 or less zones: give nothing
    def manage_detect_ping_message(self, m, addr):
        requestor_zone = m.get('from_zone', None)
        if requestor_zone is None:
            return
        
        my_self = self._get_myself_read_only()
        my_node_data = self.create_alive_msg(my_self)
        
        r = {'type': PACKET_TYPES.DETECT_PONG, 'node': my_node_data, 'from_zone': self.zone}
        ret_msg = jsoner.dumps(r)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        encrypter = libstore.get_encrypter()
        
        answer_allowed = False
        # Look if we should answer or not
        if requestor_zone == self.zone:
            answer_allowed = True
        else:
            if zonemgr.is_top_zone_from(self.zone, requestor_zone):
                answer_allowed = True
            else:  # Lower zone: only if we are a proxy and from a directly lower zone
                if self.is_proxy:
                    answer_allowed = zonemgr.is_direct_sub_zone_from(self.zone, requestor_zone)
        
        if not answer_allowed:
            logger.info('Will not answer to node %s' % m)
            return
        
        response_zone = requestor_zone
        # If the zone from the other side is too high for us, we mustch switch to our own zone
        # instead
        # if it's lower, keep the other zone, as our own won't be available for him
        if zonemgr.is_top_zone_from(self.zone, requestor_zone):
            response_zone = self.zone
        enc_ret_msg = encrypter.encrypt(ret_msg, dest_zone_name=response_zone)
        sock.sendto(enc_ret_msg, addr)
        sock.close()
        logger.info("Detect back: return back message (from %s): %s" % (ret_msg, m))
    
    
    # launch a broadcast (UDP) and wait 5s for returns, and give all answers from others daemons
    def launch_gossip_detect_ping(self, timeout):
        logger.info('Launching UDP detection with a %d second timeout' % timeout)
        r = []
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        p = '{"type":"%s", "from_zone":"%s"}' % (PACKET_TYPES.DETECT_PING, self.zone)
        encrypter = libstore.get_encrypter()
        enc_p = encrypter.encrypt(p, dest_zone_name=self.zone)
        s.sendto(enc_p, ('<broadcast>', 6768))
        # Note: a socket timeout start from the recvfrom call
        # so we must compute the time where we should finish
        start = time.time()
        end = start + timeout
        
        while True:
            now = time.time()
            remaining_time = end - now
            # Maybe we did get bac in time a LOT
            if remaining_time > timeout:
                break
            # No more time: break
            if remaining_time < 0:
                break
            logger.debug('UDP detection Remaining time: %.2f' % remaining_time)
            s.settimeout(remaining_time)
            try:
                data, addr = s.recvfrom(65507)
            except socket.timeout:
                logger.info('UDP detection: no response after: %.2f' % (time.time() - start))
                continue
            logger.debug('RECEIVE detect-ping response: %s' % data)
            try:
                d_str = encrypter.decrypt(data)
                d = jsoner.loads(d_str)
            # If bad json, skip it
            except ValueError as exp:
                logger.error('Cannot load ping detection package: %s' % exp)
                continue
            logger.info('UDP detected node: %s' % d)
            # if not a detect-pong package, I don't want it
            _type = d.get('type', '')
            if _type != PACKET_TYPES.DETECT_PONG:
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
        
        logger.info('UDP detection done after %dseconds. %d nodes are detected on the network.' % (timeout, len(r)))
        return r
    
    
    # Randomly push some gossip broadcast messages and send them to
    # KGOSSIP others nodes
    # consume: if True (default) then a message will be decremented
    def __do_gossip_push(self, dest, consume=True):
        messages = deque()
        message = ''
        to_del = []
        stack = []  # not deque because we cannot json it
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
                    # Increase message send number but only if we need to consume it (our zone send)
                    b['send'] += 1
                    send = b['send']
                    if send >= KGOSSIP:
                        to_del.append(b)
                # NOTE: maybe this message will make the current stack too big
                # if so we will get back to the old version and create a new stack
                bmsg = b['msg']
                stack.append(bmsg)
                message = jsoner.dumps(stack)
                # Maybe we are now too large and we do not have just one
                # fucking big message, so we fail back to the old_message that was
                # in the good size and send it now
                if len(message) > 1400 and len(stack) != 1:
                    # Stop this message, stock the previous version, and start a new stack
                    messages.append(old_message)
                    # reset with just the new packet
                    stack = [bmsg]
                    message = jsoner.dumps(stack)
        # always stack the last one if we did create more than 1
        # or just the first if it was small
        if message != '':
            messages.append(message)
        
        # Maybe there is no messages to send
        if len(messages) == 0:
            return
        
        with broadcaster.broadcasts_lock:
            # Clean too much broadcasted messages
            for b in to_del:
                broadcaster.broadcasts.remove(b)
        
        addr = dest['public_addr']
        port = dest['port']
        zone_name = dest['zone']
        # if the other node is from a higher realm, we cannot talk to it with it's own key (we don't have it)
        if zonemgr.is_top_zone_from(self.zone, zone_name):
            zone_name = self.zone
        total_size = 0
        sock = None
        # and go for it!
        try:
            encrypter = libstore.get_encrypter()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            for message in messages:
                logger.debug('BROADCAST: sending message: (len=%d) %s' % (len(message), message))
                enc_message = encrypter.encrypt(message, dest_zone_name=zone_name)
                total_size += len(enc_message)
                sock.sendto(enc_message, (addr, port))
            logger.debug('BROADCAST: sent %d messages (total size=%d) to %s:%s (uuid=%s  display_name=%s)' % (len(messages), total_size, addr, port, dest['uuid'], dest['display_name']))
        except (socket.timeout, socket.gaierror) as exp:
            logger.error("ERROR: cannot sent the UDP message of len %d to %s: %s" % (len(message), dest['uuid'], exp))
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
    
    
    def _get_seeds_nodes(self):
        if len(self.seeds) == 0:
            logger.info("We do not have any seeds to join at startup.")
            return None
        
        res = []
        for e in self.seeds:
            elts = e.split(':')
            addr = elts[0]
            port = self.port
            if len(elts) > 1:
                port = int(elts[1])
            res.append((addr, port))
        
        return res
    
    
    def _wait_join_nodes(self, other_nodes):
        while not stopper.is_stop():
            logger.log('JOINING myself %s is joining %s nodes' % (self.name, other_nodes))
            nb = 0
            for other in other_nodes:
                r = self.do_push_pull(other)
                if r:
                    nb += 1
                # Do not merge with more than KGOSSIP distant nodes
                if nb > KGOSSIP:
                    continue
            # If we got enough nodes, we exit
            if len(self.nodes) != 1 or stopper.is_stop() or self.bootstrap:
                return
            # Do not hummer the cpu....
            time.sleep(0.1)
    
    
    # Will try to join a node cluster and do a push-pull with at least one of them
    def join_bootstrap(self, force_wait_proxy):
        # If we have seeds nodes, respect them
        seeds_nodes = self._get_seeds_nodes()
        if seeds_nodes is not None:
            logger.info('We have seeds nodes that we need to join before start')
            self._wait_join_nodes(seeds_nodes)
            return
        
        # If we do not have seeds, maybe we are asked to auto-detect nodes
        # and then join them
        if force_wait_proxy:
            if self.is_proxy:
                logger.info('We skip the auto-detect joining phase as we are ourselve a proxy node')
                return
            logger.info('We are asked to auto-detect others nodes before start')
            # Wait un til we listen about at least one proxy node
            while not stopper.is_stop():
                detected_nodes = self.launch_gossip_detect_ping(5)  # wait 5s to get return, plenty time
                # we sort to be sure all nodes will join the same node, and so join alltogether
                proxy_detected = sorted([node for node in detected_nodes if node['is_proxy']], key=lambda n: n['uuid'])
                if proxy_detected:
                    logger.info('Did founded %s proxy nodes, trying to join them' % (len(proxy_detected)))
                    # the wait join only need (addr, port)
                    proxy_nodes_extract = [(node['public_addr'], node['port']) for node in proxy_detected]
                    self._wait_join_nodes(proxy_nodes_extract)
                    return
                time.sleep(0.1)
    
    
    # Go launch a push-pull to another node. We will sync all our nodes
    # entries, and each other will be able to learn new nodes and so
    # launch gossip broadcasts if need
    # We push pull:
    # * our own zone
    # * the upper zone
    # * NEVER lower zone. They will connect to us
    def do_push_pull(self, other):
        nodes = self.nodes
        sub_zones = zonemgr.get_sub_zones_from(self.zone)
        nodes_to_send = {}
        for (nuuid, node) in nodes.items():
            nzone = node['zone']
            if nzone != self.zone and nzone not in sub_zones:
                # skip this node
                continue
            # ok in the good zone (our or sub)
            nodes_to_send[nuuid] = node
        
        with self.events_lock:
            events = copy.deepcopy(self.events)
        
        logger.debug('do_push_pull:: giving %s informations about nodes: %s' % (other[0], [n['name'] for n in nodes_to_send.values()]))
        m = {'type': 'push-pull-msg', 'ask-from-zone': self.zone, 'nodes': nodes_to_send, 'events': events}
        message = jsoner.dumps(m)
        
        (addr, port) = other
        
        uri = 'http://%s:%s/agent/push-pull' % (addr, port)
        payload = {'msg': message}
        try:
            r = httper.get(uri, params=payload)
            logger.debug("push-pull response", r)
            try:
                back = jsoner.loads(r)
            except ValueError as exp:
                logger.error('ERROR CONNECTING TO %s:%s' % other, exp)
                return False
            # Maybe we were not autorized
            if 'error' in back:
                logger.error('Cannot push/pull with node %s: %s' % (addr, back['error']))
                return False
            logger.debug('do_push_pull: get return from %s:%s' % (other[0], back))
            if 'nodes' not in back:
                logger.error('do_push_pull: back message do not have nodes entry: %s' % back)
                return False
            self.merge_nodes(back['nodes'])
            self.merge_events(back.get('events', {}))
            return True
        except get_http_exceptions() as exp:
            logger.error('[push-pull] ERROR CONNECTING TO %s:%s' % other, exp)
            return False
    
    
    # An other node did push-pull us, and we did load it's nodes,
    # but now we should give back only nodes that the other zone
    # have the right:
    # * same zone as us: give all we know about
    # * top zone: can be the case if the top try to join us, in normal cases only lower zone ask upper zones (give all)
    # * direct sub zones: give only our zone proxy nodes
    #   * no the other nodes of my zones, they don't have to know my zone detail
    #   * not my top zones of course, same reason, even proxy nodes, they need to talk to me only
    #   * not the other sub zones of my, because they don't have to see which who I am linked (can be an other customer for example)
    #     * but if the sub-zone is their own, then ok give it
    # * too much sub zones: give nothing
    def get_nodes_for_push_pull_response(self, other_node_zone):
        logger.debug('PUSH-PULL: get a push pull from a node zone: %s' % other_node_zone)
        # Same zone: give all we know about
        if other_node_zone == self.zone:
            logger.debug('PUSH-PULL same zone ask us, give back all we know about')
            nodes = self.nodes
            return nodes
        
        # Top zones can see all of us
        top_zones = zonemgr.get_top_zones_from(self.zone)
        logger.debug('PUSH-PULL: MY TOP ZONE (from %s) : %s' % (self.zone, top_zones))
        if other_node_zone in top_zones:
            nodes = self.nodes
            return nodes
        
        # Not my zone and not a top zone, so lower zone. Must be a proxy to allow to give some infos
        if not self.is_proxy:
            logger.info('PUSH-PULL: another node ask us a push_pull from a not my zone or top zone: %s' % other_node_zone)
            return None
        
        # But only answer if it's from a directly sub zone (low-low zone should not see us)
        # give my zone proxy nodes
        if zonemgr.is_direct_sub_zone_from(self.zone, other_node_zone):
            my_zone_proxies_and_its_zone = {}
            for (nuuid, node) in self.nodes.items():
                if node['is_proxy'] and node['zone'] == self.zone:
                    my_zone_proxies_and_its_zone[nuuid] = node
                    logger.debug('PUSH-PULL: give back data about proxy node of my own zone: %s' % node['name'])
                    continue
                if node['zone'] == other_node_zone:
                    my_zone_proxies_and_its_zone[nuuid] = node
                    logger.debug('PUSH-PULL: give back data about a node of the caller zone: %s' % node['name'])
                    continue
            return my_zone_proxies_and_its_zone
        
        # Other level (brother like zones or sub-sub zones)
        logger.warning('SECURITY: a node from an unallowed zone %s did ask us push_pull' % other_node_zone)
        return None
    
    
    # suspect nodes are set with a suspect_time entry. If it's too old,
    # set the node as dead, and broadcast the information to everyone
    def look_at_deads(self):
        # suspect a node for 5 * log(n+1) * interval
        node_scale = math.ceil(math.log10(float(len(self.nodes) + 1)))
        probe_interval = 1
        suspicion_mult = 5
        suspect_timeout = suspicion_mult * node_scale * probe_interval
        leave_timeout = suspect_timeout * 30  # something like 300s
        
        now = int(time.time())
        for node in self.nodes.values():
            # Only look at suspect nodes of course...
            if node['state'] != NODE_STATES.SUSPECT:
                continue
            stime = node.get('suspect_time', now)
            if stime < (now - suspect_timeout):
                logger.info("SUSPECT: NODE", node['name'], node['incarnation'], node['state'], "is NOW DEAD")
                node['state'] = NODE_STATES.DEAD
                # warn internal elements
                self.node_did_change(node['uuid'])
                # Save this change into our history
                self.__add_node_state_change_history_entry(node, NODE_STATES.SUSPECT, NODE_STATES.DEAD)
                # and external ones
                self.stack_dead_broadcast(node)
        
        # Now for leave nodes, this time we will really remove the entry from our nodes
        to_del = []
        # with self.nodes_lock:
        for node in self.nodes.values():
            # Only look at suspect nodes of course...
            if node['state'] != NODE_STATES.LEAVE:
                continue
            ltime = node.get('leave_time', now)
            logger.debug("LEAVE TIME for node %s %s %s %s" % (node['name'], ltime, now - leave_timeout, (now - leave_timeout) - ltime))
            if ltime < (now - leave_timeout):
                logger.info("LEAVE: NODE", node['name'], node['incarnation'], node['state'], "is now definitivly leaved. We remove it from our nodes")
                to_del.append(node['uuid'])
        # now really remove them from our list :)
        for uuid in to_del:
            self.delete_node(uuid)
    
    
    @staticmethod
    def __get_node_basic_msg(node):
        return {
            'name'       : node['name'], 'display_name': node.get('display_name', ''),
            'public_addr': node['public_addr'], 'local_addr': node['local_addr'],
            'port'       : node['port'], 'uuid': node['uuid'],
            'incarnation': node['incarnation'], 'groups': node.get('groups', []),
            'services'   : node['services'], 'checks': node['checks'],
            'zone'       : node.get('zone', ''), 'is_proxy': node.get('is_proxy', False),
        }
    
    
    ########## Message managment
    def create_alive_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = PACKET_TYPES.ALIVE
        r['state'] = NODE_STATES.ALIVE
        return r
    
    
    def create_event_msg(self, payload):
        return {'type'   : 'event', 'from': self.uuid, 'payload': payload, 'ctime': int(time.time()),
                'eventid': get_uuid()}
    
    
    def create_suspect_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = PACKET_TYPES.SUSPECT
        r['state'] = NODE_STATES.SUSPECT
        return r
    
    
    def create_dead_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = PACKET_TYPES.DEAD
        r['state'] = NODE_STATES.DEAD
        return r
    
    
    def create_leave_msg(self, node):
        r = self.__get_node_basic_msg(node)
        r['type'] = PACKET_TYPES.LEAVE
        r['state'] = NODE_STATES.LEAVE
        return r
    
    
    def stack_alive_broadcast(self, node):
        msg = self.create_alive_msg(node)
        # Node messages are before all others
        b = {'send': 0, 'msg': msg, 'prioritary': True}
        broadcaster.append(b)
        # Also send it to the websocket if there
        self.forward_to_websocket(msg)
        return
    
    
    def stack_event_broadcast(self, payload, prioritary=False):
        msg = self.create_event_msg(payload)
        b = {'send': 0, 'msg': msg, 'prioritary': prioritary}
        broadcaster.append(b)
        # save it in our events so we know we already have it
        self.add_event(msg)
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
    
    
    @staticmethod
    def forward_to_websocket(msg):
        websocketmgr.forward({'channel': 'gossip', 'payload': msg})
    
    
    # We want to send a generic message to an other node.
    # we must know about it, and we must check which gossip key to
    # use for this
    # maybe we need to exchange to a specific port (like for executor)
    def send_message_to_other(self, dest_uuid, message, force_addr=None):
        if dest_uuid == self.uuid:  # me? skip this
            return
        
        dest_node = self.nodes.get(dest_uuid, None)
        # maybe the other node did disapear
        if dest_node is None:
            return
        if not force_addr:
            dest_addr = dest_node['public_addr']
            dest_port = dest_node['port']
        else:
            dest_addr, dest_port = force_addr
        dest_zone = dest_node['zone']
        # If the other is in a top level, we don't have it's zone key, use our
        if zonemgr.is_top_zone_from(self.zone, dest_zone):
            dest_zone = self.zone
        flat_message = jsoner.dumps(message)
        try:
            # Closing context: make a context that always exit when done
            with closing_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:  # UDP
                encrypter = libstore.get_encrypter()
                encrypted_message = encrypter.encrypt(flat_message, dest_zone_name=dest_zone)
                sock.sendto(encrypted_message, (dest_addr, dest_port))
            logger.debug('Sending message to (%s) (type:%s)' % (dest_node['uuid'], message['type']))
        except (socket.timeout, socket.gaierror) as exp:
            logger.error('Cannot Send message to (%s) (type:%s): %s' % (dest_node['uuid'], message['type'], exp))
    
    
    # We did receive a UDP message from the listener, look for it
    def manage_message(self, message_type, message, source_addr):
        if message_type == PACKET_TYPES.PING:
            gossiper.manage_ping_message(message, source_addr)
        
        elif message_type == PACKET_TYPES.PING_RELAY:
            gossiper.manage_ping_relay_message(message, source_addr)
        
        elif message_type == PACKET_TYPES.DETECT_PING:
            gossiper.manage_detect_ping_message(message, source_addr)
        
        elif message_type == PACKET_TYPES.ACK:
            pass  # do nothing, wrong route but not a problem
        
        elif message_type == PACKET_TYPES.ALIVE:
            gossiper.set_alive(message)
        
        # NOTE: the dead from other is changed into a suspect, so WE decide when it will be dead
        elif message_type in (PACKET_TYPES.SUSPECT, PACKET_TYPES.DEAD):
            gossiper.set_suspect(message)
        
        elif message_type == PACKET_TYPES.LEAVE:
            gossiper.set_leave(message)
        
        else:
            logger.error('UNKNOWN gossip message: %s' % message_type)
    
    
    def query_by_name_or_uuid(self, name_or_uuid):
        for node in self.nodes.values():
            if node['uuid'] == name_or_uuid or node['name'] == name_or_uuid or node['display_name'] == name_or_uuid:
                return node
        return None
    
    
    ############## Http interface
    # We must create http callbacks in running because
    # we must have the self object
    def export_http(self):
        from .httpdaemon import http_export, response, abort, request
        
        @http_export('/agent/name')
        def get_name():
            return jsoner.dumps(self._get_myself_read_only()['name'])
        
        
        @http_export('/agent/uuid')
        def get_name():
            return jsoner.dumps(self.uuid)
        
        
        @http_export('/agent/leave/:nuuid', protected=True)
        def set_node_leave(nuuid):
            node = self.nodes.get(nuuid, None)
            if node is None:
                logger.error('Asking us to set as leave the node %s but we cannot find it' % (nuuid))
                return abort(404, 'This node is not found')
            self.set_leave(node, force=True)
            return
        
        
        @http_export('/agent/members')
        def agent_members():
            response.content_type = 'application/json'
            return self.nodes
        
        
        @http_export('/agent/members/history', method='GET')
        def agent_members_history():
            response.content_type = 'application/json'
            r = gossiper.get_history()
            return jsoner.dumps(r)
        
        
        @http_export('/agent/join/:other', protected=True)
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
            return jsoner.dumps(r)
        
        
        @http_export('/agent/push-pull')
        def interface_push_pull():
            response.content_type = 'application/json'
            
            data = request.GET.get('msg')
            
            msg = jsoner.loads(data)
            # First: load nodes from the distant node
            t = msg.get('type', None)
            if t is None or t != 'push-pull-msg':  # bad message, skip it
                return
            
            self.merge_nodes(msg['nodes'])
            self.merge_events(msg.get('events', {}))
            
            # And look where does the message came from: if it's the same
            # zone: we can give all, but it it's a lower zone, only give our proxy nodes informations
            nodes = self.get_nodes_for_push_pull_response(msg['ask-from-zone'])
            if nodes is None:
                return jsoner.dumps({'error': 'You are not from a valid zone'})
            
            logger.debug('ASK from zone: %s and give: %s' % (msg['ask-from-zone'], nodes))
            with self.events_lock:
                events = copy.deepcopy(self.events)
            m = {'type': 'push-pull-msg', 'nodes': nodes, 'events': events}
            
            return jsoner.dumps(m)
        
        
        @http_export('/agent/detect', protected=True)
        def agent_detect():
            response.content_type = 'application/json'
            timeout = int(request.GET.get('timeout', '5'))
            try:
                nodes = self.launch_gossip_detect_ping(timeout)
            except Exception:
                logger.error('UDP detection fail: %s' % traceback.format_exc())
                raise
            return jsoner.dumps(nodes)
        
        
        # Add a group should only be allowed by unix socket (local)
        @http_export('/agent/parameters/add/groups/:gname', protected=True)
        def agent_add_group(gname):
            response.content_type = 'application/json'
            r = self.add_group(gname)
            return jsoner.dumps(r)
        
        
        # Add a group should only be allowed by unix socket (local)
        @http_export('/agent/parameters/remove/groups/:gname', protected=True)
        def agent_remove_group(gname):
            response.content_type = 'application/json'
            r = self.remove_group(gname)
            return jsoner.dumps(r)
        
        
        @http_export('/agent/zones', method='GET', protected=True)
        def get_zones():
            response.content_type = 'application/json'
            r = copy.deepcopy(zonemgr.get_zones())
            for zname, zone in r.items():
                zone['is_our_zone'] = (zname == self.zone)
                zone['have_gossip_key'] = libstore.get_encrypter().is_zone_have_key(zname)
            
            return jsoner.dumps(r)
        
        
        # Reload the key for the zone: zone_name
        @http_export('/agent/zones-keys/reload/:zone_name', method='GET', protected=True)
        def get_reload_zone_key(zone_name):
            response.content_type = 'application/json'
            encrypter = libstore.get_encrypter()
            return jsoner.dumps(encrypter.load_or_reload_key_for_zone_if_need(zone_name))
        
        
        @http_export('/agent/query/guess/:name_or_uuid', method='GET', protected=True)
        def get_query_by_name(name_or_uuid):
            response.content_type = 'application/json'
            return self.query_by_name_or_uuid(name_or_uuid)
        
        
        @http_export('/agent/ping/:node_uuid', method='GET', protected=True)
        def get_ping_node(node_uuid):
            response.content_type = 'application/json'
            node = self.get(node_uuid)
            if node is None:
                return {'error': 'No such node %s' % node_uuid}
            self.__do_ping(node)
            logger.info('NODE STATE: %s' % node['state'])
            return {'state': node['state']}
        
        
        @http_export('/agent/event/:event_type', method='GET', protected=True)
        def get_event(event_type):
            response.content_type = 'application/json'
            evt = None
            with self.events_lock:
                for (cid, e) in self.events.items():
                    e_type = e.get('payload', {}).get('type', None)
                    if e_type == event_type:
                        evt = e
            return jsoner.dumps(evt)
        
        
        @http_export('/agent/event', method='POST', protected=True)
        def agent_eval_check():
            response.content_type = 'application/json'
            event_type = request.POST.get('event_type')
            if not event_type:
                return abort(400, 'Missing event_type parameter')
            payload = {'type': event_type}
            self.stack_event_broadcast(payload, prioritary=True)
            return jsoner.dumps(True)


gossiper = Gossip()
