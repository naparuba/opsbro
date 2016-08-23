import threading
import time
import random
import math
import sys
from Queue import Queue, Empty

# ELECTION_TIMEOUT_LIMITS = (150, 300)

HEARTHBEAT_INTERVAL = 150

ELECTION_PERIOD = 1000  # 1s for a candidate to wait for others response


class RaftNode(object):
    def __init__(self, i):
        self.i = i
        self.raft_state = self.state = 'follower'
        self.term = 0
        
        self.HEARTHBEAT_TIMEOUT = 1000
        self.ELECTION_TIMEOUT_LIMITS = (150, 300)
        
        self.leader = None
        # inner state that vary between :
        # follower=>wait_for_candidate=>candidate=>leader
        #                             =>did_vote        
        self.set_state('follower')
        
        # some various timers
        self.t_to_candidate = 0
        
        # get the number of vote we have
        self.nb_vote = 0
        
        # and the election turn we have. This will increase the
        # election_timeout when we go in candidate state
        self.election_turn = 0
        
        self.interrrupted = False
        
        self.last_leader_talk = 0
    
    
    def stop(self):
        self.set_state('leaved')
        self.interrrupted = True
    
    
    def __str__(self):
        return '(%d:%s)' % (self.i, self.state)
    
    
    def tick(self, nodes):
        pass
    
    
    def set_state(self, state):
        print self.i, "SWITCHING from ", self.state, "TO ", state
        self.state = state
    
    
    # Send a message to all other nodes, but not me
    def send_to_others(self, nodes, m):
        for d in nodes:
            other = d['node']
            if other.i != self.i:
                d['queue'].put(m)
    
    
    # Return a ok vote to the candidate_id node
    def give_vote_to(self, nodes, candidate_id):
        for d in nodes:
            if d['node'].i == candidate_id:
                m_ret = {'type': 'vote', 'from': self.i}
                d['queue'].put(m_ret)
    
    
    # someone did ask us t ovote for him. We must not already have a leader, and
    # we must be a follower or not already a candidate
    def manage_ask_vote(self, m, nodes):
        if self.leader is None and self.state in ['follower', 'wait_for_candidate']:  # no leader? ok vote for you guy!
            self.set_state('did-vote')
            candidate_id = m['candidate']
            self.give_vote_to(nodes, candidate_id)
    
    
    # Someone did vote for me, but I must be a candidate to accept this
    def manage_vote(self, m, nodes):
        if self.state != 'candidate':  # exit if not already a candidate
            return
        
        self.nb_vote += 1
        quorum_size = math.ceil(float(len(nodes) + 1) / 2)
        # print "I (%d) got a new voter %d" % (n.i, self.nb_vote)
        if self.nb_vote >= quorum_size:
            print "I (%d) did win the vote! with %d" % (self.i, self.nb_vote)
            self.set_state('leader')
            # warn every one that I am the leader
            m_broad = {'type': 'leader-elected', 'leader': self.i}
            self.send_to_others(nodes, m_broad)
    
    
    # A new leader is elected, take it
    def manage_leader_elected(self, m, nodes):
        elected_id = m['leader']
        if elected_id == self.i:
            # that's me, I alrady know about it...
            return
        
        if self.state == 'leader':  # another leader?
            print "TO MANAGE" * 100, self.i, elected_id, self.term
        elif self.state in ['candidate', 'follower', 'did-vote']:  #
            # print "GOT A LEADER JUST ELECTED", self.i, elected_id
            self.leader = None
            for d in nodes:
                if d['node'].i == elected_id:
                    self.leader = d['node']
            # Maybe it was a fake leader?
            if self.leader is None:
                return
            
            if self.state == 'candidate':
                print "I (%d) got a new leader (%d) before me, and I respect it" % (self.i, self.leader.i)
            self.nb_vote = 0
            self.set_state('follower')
            self.t_to_candidate = 0
            self.last_leader_talk = time.time()
    
    
    # A new leader is elected, take it
    def manage_leader_heartbeat(self, m, nodes):
        leader_id = m['leader']
        if self.leader is None:
            # TODO: get the new leader? only if term is possible of course
            return
        if leader_id != self.leader.i:
            print "NOT THE GOOD LEADER ASK US? WTF"
            sys.exit(2)
        
        if self.state != 'follower':
            print "A leader ask me to ping but I am not a follower"
            return
        print "Acception leader ping"
        # Ok accept this leader ping
        self.last_leader_talk = time.time()
    
    
    def look_for_candidated(self, nodes):
        if time.time() > self.t_to_candidate:
            print "N %d is going to be a candidate!" % self.i, self.state, self.leader
            # self.state = self.raft_state = 'candidate'
            self.set_state('candidate')
            self.nb_vote = 1  # I vote for me!
            possible_voters = nodes[:]
            random.shuffle(possible_voters)  # so not every one is asking the same on the same time
            m = {'type': 'ask-vote', 'candidate': self.i}
            self.send_to_others(possible_voters, m)
    
    
    # someone did ask us t ovote for him. We must not already have a leader, and
    # we must be a follower or not already a candidate
    def launch_heartbeat_to_others(self, nodes):
        m = {'type': 'leader-heartbeat', 'leader': self.i}
        self.send_to_others(nodes, m)
    
    
    # We did fail to elect someone, so we increase the election_turn
    # so we will wait more for being candidate.
    # also reset the states
    def fail_to_elect(self):
        print "Fail to elect, inscrease election turn"
        self.election_turn += 1
        self.reset()
    
    
    # Get back to default values for vote things :)
    def reset(self):
        self.nb_vote = 0
        self.set_state('follower')
        self.t_to_candidate = 0
        self.leader = None
        self.last_leader_talk = 0
    
    
    def main(self, q, nodes):
        while not self.interrrupted:
            self.node_loop(q, nodes)
            if self.state not in ['did-vote', 'follower']:
                print "END Of loop", self.state, self.term
            if self.state == 'leader':
                print "I AM STILL THE LEADER OF THE TERM", self.term
                # time.sleep(1)
                continue
            # maybe we are not the leader and so we must look if localy
            # we are ok
            if self.state in ['follower', 'candidate', 'did-vote']:
                if self.leader is not None:
                    continue
                else:
                    self.fail_to_elect()
                    continue
    
    
    def node_loop(self, q, nodes):
        time.sleep(2)
        start = time.time()
        
        n = self
        
        # print "Go run node", n.i, n.state
        # print 'All nodes', ','.join([str(e['node']) for e in nodes])
        # print n
        
        while not self.interrrupted:  # time.time() < start + (self.HEARTHBEAT_TIMEOUT/1000.0)*2:
            # look for message before looking for a new state :)
            try:
                r = q.get_nowait()
            except Empty:
                r = ''
            if r:
                m = r
                
                # print " %d I got a message: %s" % (n.i, m)
                
                # Someone ask us for voting for them. We can only if we got no valid leader
                # and we are a follower or not until a candidate
                if m['type'] == 'ask-vote':
                    self.manage_ask_vote(m, nodes)
                if m['type'] == 'vote':  # someone did vote for me?
                    self.manage_vote(m, nodes)
                # someone win the match, respect it                                
                if m['type'] == 'leader-elected':
                    self.manage_leader_elected(m, nodes)
                # a leader just ping me :)
                if m['type'] == 'leader-heartbeat':
                    self.manage_leader_heartbeat(m, nodes)
                # loop as fast as possible to get a new message now
                continue
            
            print "LOOP", self, "leader", self.leader
            # If we are a follower witohout a leader, it means we are in the begining of our job
            # and we need to see when we will start to be a candidate
            if self.leader == None and self.state == 'follower':
                low_election_timeout, high_election_timout = self.ELECTION_TIMEOUT_LIMITS
                # print "INCREASING LOOP", 2**self.election_turn, high_election_timout * (2**self.election_turn)
                # if high_election_timout > self.HEARTHBEAT_TIMEOUT:
                #    print 'WARNING, your election timeout is getting too high to be viable'
                # high_election_timout = self.HEARTHBEAT_TIMEOUT
                # os._exit(2)
                
                # ask for a timeout between 150 and 300ms                    
                election_timeout = random.randint(low_election_timeout, high_election_timout) * 0.001
                self.t_to_candidate = time.time() + election_timeout
                self.set_state('wait_for_candidate')
            
            # if we have a leader and we are a follower, we must look if the leader
            # did talk to us lately. If not, we start a new term
            elif self.leader is not None and self.state == 'follower':
                now = time.time()
                if now > self.last_leader_talk + self.HEARTHBEAT_TIMEOUT / 1000:
                    print self.i, "my leader is too old, I refute it"
                    self.leader = None
            
            elif self.state == 'wait_for_candidate':
                self.look_for_candidated(nodes)
            
            # If I am the leader, we ping other so we respect us
            elif self.state == 'leader':
                self.launch_heartbeat_to_others(nodes)
            
            time.sleep(0.01)


N = 3

nodes = [{'node': RaftNode(i), 'queue': Queue()} for i in range(N)]


def do_the_job(LOOP):
    # nodes = [{'node':RaftNode(i), 'queue': Queue()} for i in range(N)]
    
    threads = []
    for d in nodes:
        n = d['node']
        q = d['queue']
        t = threading.Thread(None, target=n.main, name='node-%d' % n.i, args=(q, nodes))
        t.daemon = True
        t.start()
        threads.append(t)
    
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
    
    print "Candidate density::", LOOP, 300 * (2 ** LOOP) / float(N), "ms", "& number of candidate in this loop (%d)" % LOOP, len([d for d in nodes if d['node'].state in ('candidate', 'leader')])
    if leader is not None:
        print "Good job jim", "LOOP", LOOP
        sys.exit(0)
    
    print "No leader, max vote is", max_vote


if __name__ == '__main__':
    LOOP = 0
    while True:
        LOOP += 1
        # Start with basic election
        do_the_job(LOOP)
        for d in nodes:
            n = d['node']
            n.fail_to_elect()
