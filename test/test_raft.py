#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import threading
from multiprocessing import cpu_count, Process

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
        return list(ALL_NODES.keys())  # list for python3
    
    
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
        for node_uuid in range(N):
            layer = TestRaftLayer(node_uuid)
            manager = RaftManager(layer)
            ALL_NODES[node_uuid] = manager
    
    
    def _reset_stats(self):
        self.stats = {'votes': {}, 'election_turn': {}, 'frozen_number': {}, 'is_frozen': {True: 0, False: 0}, 'with_leader': {True: 0, False: 0}}
    
    
    def _compute_stats(self):
        self._reset_stats()
        
        for (node_uuid, manager) in ALL_NODES.items():
            raft_node = manager.raft_node
            state = raft_node._state
            cprint("Node: %s is %s" % (node_uuid, state))
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
        self._compute_stats()
        logger.info('\n' * 10 + "Computed stats:" + '\n' * 10)
        logger.info('%s' % self.stats)
        return self.stats.get(state, 0)
    
    
    def get_number_of_election_turns(self):
        return len(self.stats['election_turn'])


    def launch(self):
        for (node_uuid, manager) in ALL_NODES.items():
            t = threading.Thread(None, target=manager.do_raft_thread, name='node-%d' % node_uuid)
            t.daemon = True
            t.start()
        self.start = time.time()
    
    
    def stop(self):
        for (node_uuid, manager) in ALL_NODES.items():
            cprint("STOPPING: %s" % node_uuid)
            manager.stop()
    
    
    # Create N nodes with their own thread, and wait some seconds 
    def create_and_wait(self, N=3, wait=3):
        self.create(N)
        self.launch()
        
        start = time.time()
        while True:
            now = time.time()
            self._compute_stats()
            
            nb_leader = self.count('leader')
            nb_followers = self.count('follower')
            
            if now > start + wait:
                err = 'Election timeout after %s seconds: nbleader=%s  nbfollower=%s   electionturn=%s' % (wait, nb_leader, nb_followers, 33)
                cprint('ERROR: %s' % err)
                os._exit(2)  # fast kill
            
            cprint("test_raft_large_leader_election:: Looking if we really got a leader, and only one")
            
            if nb_leader == 1 and nb_followers == N - 1:
                if self.get_number_of_election_turns() != 1:
                    cprint('FAIL: Election did SUCCESS but the election turn is not stable: nbleader=%s  nbfollower=%s   electionturn=%s after %.3fsec' % (nb_leader, nb_followers, self.get_number_of_election_turns(), time.time() - start))
                    cprint(str(self.stats))
                    os._exit(2)  # fast kill
                # Ok valid election turns
                cprint('Election did SUCCESS : nbleader=%s  nbfollower=%s   electionturn=%s after %.3fsec' % (nb_leader, nb_followers, 33, time.time() - start))
                cprint(str(self.stats))
                os._exit(0)
            cprint("Current: %.3f %s %s %s" % (time.time() - start, nb_leader, nb_followers, 33))
            time.sleep(0.5)
    
    
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
        
        NB_NODES_BY_CPU = int(os.environ.get('NB_NODES_BY_CPU', '75'))
        TEST_TIMEOUT = int(os.environ.get('TEST_TIMEOUT', '30'))
        N = NB_NODES_BY_CPU  # * NB_CPUS
        wait = TEST_TIMEOUT  # for very slow computing like travis?
        
        # launch this test as a sub process so we can kill it as fast as possible when finish (no close and such log things)
        process = Process(None, target=self.create_and_wait, args=(N, wait))
        process.start()
        process.join(wait + 3)
        if process.is_alive():
            os.kill(process.pid, 9)  # KILL
            raise Exception('The process did timeout after %s seconds' % (wait + 3))
        if process.exitcode != 0:
            raise Exception('The process did fail with return code: %s' % process.exitcode)
        cprint('OK: the process did exit well')


if __name__ == '__main__':
    unittest.main()
