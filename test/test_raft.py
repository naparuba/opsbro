#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import threading
from multiprocessing import cpu_count

NB_CPUS = cpu_count()

from opsbro_test import *
from opsbro.raft import RaftLayer, RaftManager
from opsbro.log import cprint

NB_NODES = 3

ALL_NODES = {}


class TestRaftLayer(RaftLayer):
    def __init__(self, node_uuid):
        global NB_NODES
        super(TestRaftLayer, self).__init__()
        self.uuid = node_uuid
    
    
    def get_nodes_uuids(self):
        global ALL_NODES
        return ALL_NODES.keys()
    
    
    def send_raft_message(self, node_uuid, msg):
        if node_uuid == self.uuid:
            return  # not to our selve
        other_manager = ALL_NODES[node_uuid]
        logger.info('I %s give a message (%s) to %s' % (self.uuid, msg['type'], node_uuid))
        other_manager.stack_message(msg, None)
    
    
    def get_my_uuid(self):
        return self.uuid
    
    
    def get_other_node(self, node_uuid):
        raise NotImplemented()


class RaftQueue():
    def __init__(self):
        self.queue = []
        self.lock = threading.RLock()
    
    
    def put(self, m):
        with self.lock:
            self.queue.append(m)
    
    
    def get(self):
        with self.lock:
            if len(self.queue) == 0:
                return {}
            m = self.queue.pop()
        return m


class TestRaft(OpsBroTest):
    def tearDown(self):
        self.stop()
    
    
    def create(self, N=3):
        global ALL_NODES
        
        ALL_NODES.clear()  # reset other tests
        for node_uuid in xrange(N):
            layer = TestRaftLayer(node_uuid)
            manager = RaftManager(layer)
            ALL_NODES[node_uuid] = manager
    
    
    def compute_stats(self):
        self.stats = {'votes': {}, 'election_turn': {}, 'frozen_number': {}, 'is_frozen': {True: 0, False: 0}, 'with_leader': {True: 0, False: 0}}
        
        for (node_uuid, manager) in ALL_NODES.items():
            raft_node = manager.raft_node
            state = raft_node._state
            print "Node: %s is %s" % (node_uuid, state)
            if state not in self.stats:
                self.stats[state] = 0
            self.stats[state] += 1
            # Save candidate votes
            if state == 'candidate':
                self.stats['votes'][node_uuid] = raft_node._nb_vote_received
            # Display election turns
            election_turn = raft_node._election_turn
            if election_turn not in self.stats['election_turn']:
                self.stats['election_turn'][election_turn] = 0
            self.stats['election_turn'][election_turn] += 1
            
            # and frozen number
            # if n.frozen_number not in self.stats['frozen_number']:
            #    self.stats['frozen_number'][n.frozen_number] = 0
            # self.stats['frozen_number'][n.frozen_number] += 1
            
            # self.stats['is_frozen'][n.is_frozen] += 1
            self.stats['with_leader'][(raft_node._leader is not None)] += 1
    
    
    def count(self, state):
        # hummering the stats so we are up to date
        self.compute_stats()
        logger.info('\n' * 10 + "Computed stats:" + '\n' * 10)
        logger.info('%s' % self.stats)
        return self.stats.get(state, 0)
    
    
    def launch(self):
        for (node_uuid, manager) in ALL_NODES.items():
            t = threading.Thread(None, target=manager.do_raft_thread, name='node-%d' % node_uuid)
            t.daemon = True
            t.start()
        self.start = time.time()
    
    
    def stop(self):
        for (node_uuid, manager) in ALL_NODES.items():
            print "STOPPING: %s" % node_uuid
            manager.stop()
    
    
    # Create N nodes with their own thread, and wait some seconds 
    def create_and_wait(self, N=3, wait=3):
        self.create(N)
        self.launch()
        
        time.sleep(wait)
    
    
    def get_leader(self):
        for d in self.nodes:
            n = d['node']
            if n.state == 'leader':
                return n
    
    
    def get_all_state(self, state):
        res = []
        for d in self.nodes:
            n = d['node']
            if n.state == state:
                res.append(n)
        return res
    
    
    ############################### TESTS
    def test_raft_simple_leader_election(self):
        self.create_and_wait(N=3, wait=3)
        
        nb_leader = self.count('leader')
        self.assert_(nb_leader == 1)
        # always clean before exiting a test
        self.stop()
    
    
    # Try with far more nodes
    def test_raft_large_leader_election(self):
        cprint("TEST: test_raft_large_leader_election")
        
        N = 75 * NB_CPUS
        W = 30  # for very slow computing like travis?
        self.create_and_wait(N=N, wait=W)
        
        cprint("test_raft_large_leader_election:: Looking if we really got a leader, and only one")
        cprint("test_raft_large_leader_election:: Number of leaders: %d" % self.count('leader'))
        self.compute_stats()
        
        nb_leader = self.count('leader')
        
        self.assert_(nb_leader == 1)
        
        # and N-1 followers
        nb_followers = self.count('follower')
        cprint("NB followers: %s" % nb_followers)
        cprint(str(self.stats))
        self.assert_(nb_followers == N - 1)


if __name__ == '__main__':
    unittest.main()
