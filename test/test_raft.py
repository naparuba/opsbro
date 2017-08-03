#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import threading

from opsbro_test import *
from opsbro.raft import RaftNode


class RaftQueue():
    def __init__(self):
        self.queue = []
        self.lock = threading.RLock()
        
    def put(self, m):
        with self.lock:
            self.queue.append(m)
    
    def get(self):
        with self.lock:
            try:
                m = self.queue.pop()
            except:
                m = {}
        return m
        
        

class TestRaft(OpsBroTest):
    def tearDown(self):
        self.stop()
    
    
    def create(self, N=3):
        self.nodes = [{'node': RaftNode(i), 'queue': RaftQueue()} for i in range(N)]
    
    
    def compute_stats(self):
        self.stats = {'votes': {}, 'election_turn': {}, 'frozen_number': {}, 'is_frozen': {True: 0, False: 0}, 'with_leader': {True: 0, False: 0}}
        
        for d in self.nodes:
            n = d['node']
            s = n.state
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
    
    
    def launch(self):
        # nodes = [{'node':RaftNode(i), 'queue': Queue()} for i in range(N)]
        
        self.threads = []
        for d in self.nodes:
            n = d['node']
            q = d['queue']
            t = threading.Thread(None, target=n.main, name='node-%d' % n.i, args=(q, self.nodes))
            t.daemon = True
            t.start()
            self.threads.append(t)
        
        self.start = time.time()
        
        return
    
    
    def stop(self):
        for d in self.nodes:
            n = d['node']
            n.stop()
        
        wait_time = 1
        for t in self.threads:
            t.join(0.01)
            wait_time -= 1
            if wait_time < 0:
                wait_time = 0.01
    
    
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
        
        self.assert_(self.count('leader') == 1)
        # always clean before exiting a test
        self.stop()
    
    
    # Try with far more nodes
    def test_raft_large_leader_election(self):
        print "TEST: test_raft_large_leader_election"
        N = 150
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
