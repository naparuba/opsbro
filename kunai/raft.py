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
        self.ELECTION_TIMEOUT_LIMITS = (150, 300)  # 150ms and 300ms for election period
        
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
        # election_timeout when we go in candidate state,
        # and if someone have a bigger election turn, it wons
        self.election_turn = 0
        
        self.interrrupted = False
        
        # When did our leader ping us to let us know it is still alive
        self.last_leader_talk = 0
        # I did send a vote, and I must be sure that I don't let too much time before have a leader
        self.vote_date = 0
        
        # Frozen date: I will be frozen for action until this time if I was set as too old
        self.end_frozen_date = 0
        self.is_frozen = False
        self.frozen_number = 0  # number of time we did get into frozen state, will increase election turn issue resolution scale
        
        # We count the number of time we did have been candidate, to change our timeouts, 1/3 will be favored, 2/3 will be with higher values
        self.candidate_nb_times = 0
        
        self.nodes = []
    
    
    # timeouts will change based on the number of elements, as s timing
    def _get_election_timeouts(self):
        ratio = math.ceil(len(self.nodes) / 100.0)
        low_limit, high_limit = self.ELECTION_TIMEOUT_LIMITS
        return low_limit * 0.001, high_limit * ratio * 0.001
    
    
    def _get_heartbeat_timeout(self):
        ratio = math.ceil(len(self.nodes) / 100.0)
        return self.HEARTHBEAT_TIMEOUT * ratio * 0.001
    
    
    def stop(self):
        self.set_state('leaved')
        self.interrrupted = True
    
    
    def __str__(self):
        return '(%d:%s)' % (self.i, self.state)
    
    
    def tick(self, nodes):
        pass
    
    
    def set_state(self, state):
        # Already the same state
        if state == self.state:
            return
        print "[%4d] %s => %s " % (self.i, self.state, state)
        self.state = state
    
    
    # Send a message to all other nodes, but not me
    def send_to_others(self, nodes, m):
        # tag the message with current election_turn
        m['election_turn'] = self.election_turn
        for d in nodes:
            other = d['node']
            if other.i != self.i:
                d['queue'].put(m)
    
    
    # Return a ok vote to the candidate_id node
    def give_vote_to(self, nodes, candidate_id):
        print "[%4d] I give a vote to %d" % (self.i, candidate_id)
        for d in nodes:
            if d['node'].i == candidate_id:
                m_ret = {'type': 'vote', 'from': self.i, 'election_turn': self.election_turn}
                d['queue'].put(m_ret)
    
    
    # Return a ok vote to the candidate_id node
    def warn_other_node_about_old_election_turn(self, nodes, other_id):
        for d in nodes:
            if d['node'].i == other_id:
                m_ret = {'type': 'warn-old-election-turn', 'from': self.i, 'election_turn': self.election_turn}
                d['queue'].put(m_ret)
    
    
    # Wrn all nodes about a new election turn
    def warn_other_nodes_about_old_election_turn(self, nodes):
        m_ret = {'type': 'warn-old-election-turn', 'from': self.i, 'election_turn': self.election_turn}
        self.send_to_others(nodes, m_ret)
    
    
    # someone did ask us t ovote for him. We must not already have a leader, and
    # we must be a follower or not already a candidate
    def manage_ask_vote(self, m, nodes):
        if self.leader is None and self.state in ['follower', 'wait_for_candidate']:  # no leader? ok vote for you guy!
            self.set_state('did-vote')
            candidate_id = m['candidate']
            self.vote_date = time.time()
            self.give_vote_to(nodes, candidate_id)
            self.candidate_id = candidate_id
    
    
    # Someone did vote for me, but I must be a candidate to accept this
    def manage_vote(self, m, nodes):
        if self.state != 'candidate':  # exit if not already a candidate
            return
        
        self.nb_vote += 1
        quorum_size = math.ceil(float(len(nodes) + 1) / 2)
        # print "I (%d) got a new voter %d" % (n.i, self.nb_vote)
        if self.nb_vote >= quorum_size:
            print "[%4d] did win the vote! with %d votes for me on a total of %d (quorum size=%d) in %.2fs" % (self.i, self.nb_vote, len(nodes), quorum_size, time.time() - self.start)
            self.set_state('leader')
            # warn every one that I am the leader
            m_broad = {'type': 'leader-elected', 'leader': self.i, 'from': self.i}
            self.send_to_others(nodes, m_broad)
    
    
    # A new leader is elected, take it
    def manage_leader_elected(self, m, nodes):
        elected_id = m['leader']
        if elected_id == self.i:
            # that's me, I already know about it...
            return
        
        if self.state == 'leader':  # another leader?
            print "TO MANAGE" * 100, self.i, elected_id, self.term
            return
        
        # Already know it
        if self.leader is not None and self.leader.i == elected_id:
            print "[%4d] Already know about this leader %s" % (self.i, elected_id)
            return
        
        if self.state in ['candidate', 'follower', 'did-vote']:  #
            # print "GOT A LEADER JUST ELECTED", self.i, elected_id
            self.leader = None
            for d in nodes:
                if d['node'].i == elected_id:
                    self.leader = d['node']
            # Maybe it was a fake leader?
            if self.leader is None:
                return
            
            if self.state == 'candidate':
                print "[%4d] got a new leader (%d) before me, and I respect it" % (self.i, self.leader.i)
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
        # print "Acception leader ping"
        # Ok accept this leader ping
        self.last_leader_talk = time.time()
    
    
    def look_for_candidated(self, nodes):
        if time.time() > self.t_to_candidate:
            print "[%4d] is going to be a candidate!" % self.i
            # self.state = self.raft_state = 'candidate'
            self.set_state('candidate')
            self.nb_vote = 1  # I vote for me!
            possible_voters = nodes[:]
            random.shuffle(possible_voters)  # so not every one is asking the same on the same time
            m = {'type': 'ask-vote', 'candidate': self.i, 'from': self.i}
            self.send_to_others(possible_voters, m)
            # set that we was a candidate this turn
            self.candidate_nb_times += 1
    
    
    # someone did ask us t ovote for him. We must not already have a leader, and
    # we must be a follower or not already a candidate
    def launch_heartbeat_to_others(self, nodes):
        t0 = time.time()
        m = {'type': 'leader-heartbeat', 'leader': self.i, 'from': self.i}
        self.send_to_others(nodes, m)
        if (time.time() - t0) > 0.1:
            print "************ [%d] TIME TO LEADER OTHERS: %.3f" % (self.i, (time.time() - t0))
    
    
    # Launch a dummy message to others, for example to be sure our election_turn is ok
    def launch_dummy_to_random_others(self, nodes):
        n = int(math.ceil(math.log(len(nodes)))) + 1
        n *= self.frozen_number  # the more we did get into frozen, the more nodes we try to sync with
        n = min(n, len(nodes))
        
        n = len(nodes)
        # try to find n nodes randomly from nodes
        to_send = []
        for i in xrange(n):
            to_send.append(random.choice(nodes))
        # Now send
        print "[%4d] SEND RANDOMLY dummy passage: %s" % (self.i, len(to_send))
        m = {'type': 'dummy', 'election_turn': self.election_turn, 'from': self.i}
        self.send_to_others(to_send, m)
    
    
    # We did fail to elect someone, so we increase the election_turn
    # so we will wait more for being candidate.
    # also reset the states
    def fail_to_elect(self):
        print "[%4d] Fail to elect, increase election turn" % self.i
        self.reset()
        self.election_turn += 1
        self.build_wait_for_candidate_phase()
    
    
    # Get back to default values for vote things :)
    def reset(self):
        self.nb_vote = 0
        self.set_state('follower')
        self.t_to_candidate = 0
        self.leader = None
        self.last_leader_talk = 0
        self.vote_date = 0
        print "[%4d] WAS CANDIDATE? %d nb times" % (self.i, self.candidate_nb_times)
    
    
    def main(self, q, nodes):
        self.nodes = nodes
        # be sure to have a specific random
        random.seed(time.time() * random.random())
        while not self.interrrupted:
            self.node_loop(q, nodes)
            # if self.state not in ['did-vote', 'follower']:
            #    print "END Of loop", self.state, self.term
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
        self.start = time.time()
        
        n = self
        
        # Start with a build of our future candidate state, so random time is genated to know when we will candidate
        self.build_wait_for_candidate_phase()
        
        while not self.interrrupted:
            # look for message before looking for a new state :)
            try:
                r = q.get_nowait()
            except Empty:
                r = {}
            except Exception, exp:
                print "ERROR: not managed: %s" % exp
                break
            
            # Look if we are still frozen
            now = time.time()
            if self.end_frozen_date != 0 and now > self.end_frozen_date:
                self.end_frozen_date = 0
                self.is_frozen = False
                print "[%4d] Exiting from freeze" % self.i
            
            if r:
                m = r
                
                # print " %d I got a message: %s" % (n.i, m)
                election_turn = m['election_turn']
                # if we are over election turn,
                if self.election_turn > election_turn:
                    # print "SKIPPING OLD ELECTION turn me=%d other=%d" % (self.election_turn, election_turn)
                    # other is old, we warn it about it
                    # print "[%4d] I warn the other nodes that the election turn can be too old, and our is %s, other is %d" % (self.i, self.election_turn, election_turn)
                    self.warn_other_node_about_old_election_turn(nodes, m['from'])
                    continue
                
                # Maybe the message is from a newer turn than ourselve, if so, close ourself, and accept the new message
                if self.election_turn < election_turn:
                    '''
                    # Ok I was too old, go in frozen mode
                    self.is_frozen = True
                    self.frozen_number += 1
                    self.end_frozen_date = time.time() + random.random()*5*self.frozen_number  # frozen for ~10s
                    print "[%4d] Going to freeze for %ss" % (self.i, self.end_frozen_date - time.time())
                    '''
                    # action can be different based on if we already did action or not
                    if self.state == 'follower' or self.state == 'wait_for_candidate':  # we did nothing, just update our turn without reset timers
                        self.election_turn = election_turn
                    else:  # candidate, leader and did-vote
                        # close our election turn only if we did talk to others, like I am a candidate, a vote or
                        print "[%4d] Our election turn is too old (our=%d other=%d) we close our election turn." % (self.i, self.election_turn, election_turn)
                        print "[%4d] swith our election turn from %d to %d" % (self.i, self.election_turn, election_turn)
                        self.fail_to_elect()
                        self.election_turn = election_turn  # get back to this election turn level
                        if self.state == 'leader' or self.state == 'candidate':
                            # If we did candidate or are leader, warn others about we did fail and do not want their vote any more
                            self.warn_other_nodes_about_old_election_turn(nodes)
                    # Randomly ask some others nodes about our election_turn
                    self.launch_dummy_to_random_others(nodes)
                
                # someone did warn that its election turn is newer than our, take it
                if m['type'] == 'warn-old-election-turn':
                    pass  # was already managed in the previous block, we did invalidate our turn
                
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
            
            # print "LOOP", self, "leader", self.leader
            # Heartbeat will be out limit of receiving from others
            hearthbeat_timeout = self._get_heartbeat_timeout()
            
            # If we did-vote, we should look that we should not let time to too much
            # and be sure the election go to the end
            if self.state == 'did-vote':
                now = time.time()
                if now > self.vote_date + hearthbeat_timeout:
                    print "[%4d] my vote is too old and I don't have any elected leader, I switch back to a new election. exchange timeout=%.3f" % (self.i, hearthbeat_timeout)
                    self.fail_to_elect()
            
            # If we are a follower witohout a leader, it means we are in the begining of our job
            # and we need to see when we will start to be a candidate
            if self.state == 'follower' and self.leader is None:
                self.build_wait_for_candidate_phase()
            
            # if we have a leader and we are a follower, we must look if the leader
            # did talk to us lately. If not, we start a new term
            elif self.state == 'follower' and self.leader is not None:
                now = time.time()
                if now > self.last_leader_talk + hearthbeat_timeout:
                    print "[%4d] my leader is too old, I refute it. exchange timeout=%.3f" % (self.i, hearthbeat_timeout)
                    # self.leader = None
                    self.fail_to_elect()
            
            elif self.state == 'wait_for_candidate':
                if not self.is_frozen:
                    self.look_for_candidated(nodes)
            
            # If I am the leader, we ping other so we respect us
            elif self.state == 'leader':
                self.launch_heartbeat_to_others(nodes)
            
            time.sleep(0.01)
    
    
    def build_wait_for_candidate_phase(self):
        low_election_timeout, high_election_timout = self._get_election_timeouts()  # self.ELECTION_TIMEOUT_LIMITS
        
        candidate_race_ratio = 1.0  # by default don't change timeouts
        # Crush 1/3 of the candidates
        if self.candidate_nb_times > 0:
            lucky_number = random.random()
            print "[%4d] Current candidate nb times: %d, lucky_number=%.2f" % (self.i, self.candidate_nb_times, lucky_number)
            if lucky_number > 0.1:
                self.candidate_nb_times = 0
        
        # Other 2/3 have 3 more time to participate
        if self.candidate_nb_times > 0:
            candidate_race_ratio = 999
            print "[%4d] We give a favor to candidature %s %s" % (self.i, low_election_timeout, high_election_timout)
        low_election_timeout /= candidate_race_ratio
        high_election_timout /= candidate_race_ratio
        if candidate_race_ratio != 1:
            print "[%4d] [%d] New timings:%s %s" % (self.i, self.election_turn, low_election_timeout, high_election_timout)
        
        # ask for a timeout between 150 and 300ms
        election_timeout = random.randint(low_election_timeout * 1000, high_election_timout * 1000)
        self.t_to_candidate = time.time() + election_timeout * 0.001
        self.set_state('wait_for_candidate')


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
