#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
from Queue import Queue,Empty

from kunai_test import *
from kunai.raft import RaftNode


class TestRaft(KunaiTest):
    def setUp(self):
        pass

    def create(self, N=3):
        self.nodes = [{'node':RaftNode(i), 'queue': Queue()} for i in range(N)]
        

    def compute_stats(self):
        self.stats = {}        
        for d in self.nodes:
            n = d['node']
            s = n.state
            if s not in self.stats:
                self.stats[s] = 0
            self.stats[s] += 1

            
    def count(self, state):
        # hummering the stats so we are up to date
        self.compute_stats()
        return self.stats.get(state, 0)

    
    def launch(self):
        #nodes = [{'node':RaftNode(i), 'queue': Queue()} for i in range(N)]

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

    
        for t in threads:
            t.join()

        # did we got a leader?
        print "RESULT FOR", LOOP
        leader = None
        max_vote = 0
        for d in nodes:
            n = d['node']
            max_vote = max(max_vote, n.nb_vote)
            if n.state == 'leader':
                if leader != None:
                    print "WE GOT 2 LEADER, WTF DID YOU DID JEAN?????"
                    sys.exit("JEAN HOW CAN YOU BREAK SUCH AN ALGO?")

                print "GOT A LEADER", n.i, 'with ', n.nb_vote, "LOOP", LOOP
                leader = n

        print "Candidate density::", LOOP, 300*(2**LOOP) / float(N), "ms", "& number of candidate in this loop (%d)" % LOOP, len([d for d in nodes if d['node'].state in ('candidate', 'leader')])
        if leader is not None:
            print "Good job jim", "LOOP", LOOP
            sys.exit(0)

        print "No leader, max vote is", max_vote


    def stop(self):
        for d in self.nodes:
            n = d['node']
            n.stop()
        for t in self.threads:
            t.join(2)


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
        N = 50
        W = 10 # for very slow computing like travis?
        self.create_and_wait(N=N, wait=W)

        print "Looking if we really got a leader, and only one"        
        self.assert_(self.count('leader') == 1)

        # and N-1 followers
        nb_followers = self.count('follower')
        print "NB followers", nb_followers
        print self.stats
        self.assert_(nb_followers == N-1)
        
        # always clean before exiting a test
        self.stop()
        
        
    
    # What is we kill some not leader nodes?
    def test_raft_kill_no_leader(self):
        N = 10
        W = 3
        self.create_and_wait(N=N, wait=W)
        print "Looking if we really got a leader, and only one"        
        self.assert_(self.count('leader') == 1)
        self.assert_(self.count('follower') == N-1)

        followers = self.get_all_state('follower')
        print followers

        NB_kill = N/2
        killed = []
        for i in range(NB_kill):
            n = followers[i]
            n.stop()
            killed.append(n)
        # wait for node to accept it
        time.sleep(1)
        
        states = [n.state for n in killed]
        # look if all are dead
        self.assert_(states.count('leaved') == NB_kill)

        # there should be still one leader
        self.assert_(self.count('leader') == 1)
        # but there are less followers now
        self.assert_(self.count('follower') == N-1-NB_kill)
        
        
        # always clean before exiting a test
        self.stop()
        

        
        
if __name__ == '__main__':
    unittest.main()
