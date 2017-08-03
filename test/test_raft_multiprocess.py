#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import multiprocessing
import threading
from multiprocessing import Process, Value, Array

from opsbro_test import *
from opsbro.raft import RaftNode


class RaftQueue():
    def __init__(self):
        self.queue = multiprocessing.Queue()
    
    
    def put(self, m):
        self.queue.put(m)
    
    
    def get(self):
        try:
            m = self.queue.get_nowait()
        except:
            m = {}
        return m


class TestRaftMultiProcess(OpsBroTest):
    def tearDown(self):
        self.stop_process()
    
    
    def create(self, N=3):
        self.nodes = [{'node': RaftNode(i), 'queue': RaftQueue()} for i in range(N)]
        for n in self.nodes:
            n['node'].export_state = Value('i', -1)
    
    
    def compute_stats(self):
        self.stats = {'votes': {}, 'election_turn': {}, 'frozen_number': {}, 'is_frozen': {True: 0, False: 0}, 'with_leader': {True: 0, False: 0}}
        
        for d in self.nodes:
            n = d['node']
            # s = n.state
            states_values_base = {'did-vote': 1, 'leader': 2, 'follower': 3, 'candidate': 4, 'wait_for_candidate': 5, 'leaved': 6}
            states_values = {}
            for (k, v) in states_values_base.iteritems():
                states_values[v] = k
            s = states_values.get(n.export_state.value)
            print "NODE EXPORT STATE: %s => %s(%s)" % (n.i, n.export_state.value, s)
            
            if s not in self.stats:
                self.stats[s] = 0
            self.stats[s] += 1
            # Save candidate votes
            if n.state == 'candidate':
                self.stats['votes'][n.i] = n.nb_vote
            # Display election turns
            if n.election_turn not in self.stats['election_turn']:
                self.stats['election_turn'][n.election_turn] = 0
            self.stats['election_turn'][n.election_turn] += 1
            
            # and frozen number
            if n.frozen_number not in self.stats['frozen_number']:
                self.stats['frozen_number'][n.frozen_number] = 0
            self.stats['frozen_number'][n.frozen_number] += 1
            
            self.stats['is_frozen'][n.is_frozen] += 1
            self.stats['with_leader'][(n.leader is not None)] += 1
    
    
    def count(self, state):
        # hummering the stats so we are up to date
        self.compute_stats()
        return self.stats.get(state, 0)
    
    
    def launch(self, wait):
        self.processes = []
        NB_PROC = multiprocessing.cpu_count()
        offset = 0
        nb_nodes = len(self.nodes)
        shard_size = nb_nodes / NB_PROC
        print "Test repartition: [nb process=%d]  [number of threads/process=%d] " % (NB_PROC, shard_size)
        for i in xrange(NB_PROC):
            t = multiprocessing.Process(None, target=self.thread_multi_loop, name='thread launcher', args=(offset, shard_size, wait))
            t.daemon = True
            t.start()
            self.processes.append(t)
            offset += shard_size
        
        self.start = time.time()
        time.sleep(wait)
        return
    
    
    def thread_multi_loop(self, shard_offset, shard_size, wait):
        self.threads = []
        for d in self.nodes[shard_offset:shard_offset + shard_size]:
            n = d['node']
            q = d['queue']
            print "[PID:%d] starting node thread: %s" % (os.getpid(), n.i)
            t = threading.Thread(None, target=n.main, name='node-%d' % n.i, args=(q, self.nodes))
            t.daemon = True
            t.start()
            self.threads.append(t)
        print "[PID:%d] Stopping %d threads" % (os.getpid(), shard_size)
        time.sleep(wait)
        self.stop_threads()
        return
    
    
    def stop_threads(self):
        for d in self.nodes:
            n = d['node']
            n.stop()
        
        wait_time = 1
        for t in self.threads:
            t.join(0.01)
            wait_time -= 1
            if wait_time < 0:
                wait_time = 0.01
    
    
    def stop_process(self):
        
        wait_time = 1
        for t in self.processes:
            t.join(0.01)
            wait_time -= 1
            if wait_time < 0:
                wait_time = 0.01
    
    
    # Create N nodes with their own thread, and wait some seconds
    def create_and_wait(self, N=3, wait=3):
        self.create(N)
        self.launch(wait)
        
        time.sleep(wait + 5)
    
    
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
    # Try with far more nodes
    def test_raft_large_leader_election(self):
        print "TEST: test_raft_large_leader_election"
        # The thread switching context is killing message propagation time because we don't have so much CPU available. So
        # we try to achieve 75 threads/CPU (it is still a lot), top should be 150/cpu, still work to do! TODO
        N = 75 * multiprocessing.cpu_count()
        W = 30  # for very slow computing like travis?
        self.create_and_wait(N=N, wait=W)
        
        print "test_raft_large_leader_election:: Looking if we really got a leader, and only one"
        print "test_raft_large_leader_election:: Number of leaders: %d" % self.count('leader')
        self.compute_stats()
        
        print "\n" * 20
        
        for d in self.nodes:
            n = d['node']
            print "== %4d %s turn=%d => candidate=%d leader=%s" % (n.i, n.state, n.election_turn, getattr(n, 'candidate_id', -1), n.leader)
        
        print >> sys.stderr, "\nSTATS: %s" % self.stats
        
        self.assert_(self.count('leader') == 1)
        
        # and N-1 followers
        nb_followers = self.count('follower')
        print "NB followers", nb_followers
        print self.stats
        self.assert_(nb_followers == N - 1)


if __name__ == '__main__':
    unittest.main()
