from __future__ import print_function
import threading
import time
import random
import math

from .util import PY3

if PY3:
    xrange = range

# ELECTION_TIMEOUT_LIMITS = (150, 300)


print_lock = threading.RLock()

from .basemanager import BaseManager
from .log import LoggerFactory
from .gossip import gossiper
from .httpdaemon import http_export, response, abort, request
from .jsonmgr import jsoner

# Global logger for this part
logger = LoggerFactory.create_logger('raft')

# If members is lower than this, raft is not allowed
RAFT_MINIMAL_MEMBERS_NB = 3


class RAFT_MESSAGES:
    WARN_OLD_ELECTION_TURN = 'raft-warn-old-election-turn'
    VOTE = 'raft-vote'
    ASK_VOTE = 'raft-ask-vote'
    LEADER_ELECTED = 'raft-leader-elected'
    LEADER_HEARTBEAT = 'raft-leader-heartbeat'
    DUMMY = 'raft-dummy'


class RAFT_STATES:
    DID_VOTE = 'did-vote'
    LEADER = 'leader'
    FOLLOWER = 'follower'
    CANDIDATE = 'candidate'
    WAIT_FOR_CANDIDATE = 'wait_for_candidate'
    LEAVED = 'leaved'


RAFT_STATE_COLORS = {RAFT_STATES.DID_VOTE          : 'blue',
                     RAFT_STATES.LEADER            : 'magenta',
                     RAFT_STATES.FOLLOWER          : 'green',
                     RAFT_STATES.CANDIDATE         : 'candidate',
                     RAFT_STATES.WAIT_FOR_CANDIDATE: 'wait_for_candidate',
                     RAFT_STATES.LEAVED            : 'grey'}

FEATURE_FLAG_FROZEN = False


class RaftNode(object):
    HEARTHBEAT_TIMEOUT = 1000
    ELECTION_TIMEOUT_LIMITS = (150, 300)  # 150ms and 300ms for election period
    
    
    def __init__(self):
        self._uuid = None
        self._state = RAFT_STATES.FOLLOWER
        self._term = 0
        
        self._leader = None
        self._pending_messages_lock = threading.RLock()
        self._pending_messages = []
        
        # inner state that vary between :
        # follower=>wait_for_candidate=>candidate=>leader
        #                             =>did_vote        
        self._set_state(RAFT_STATES.FOLLOWER)
        
        # CANDIDATE some various timers
        self._time_to_candidate = 0
        self._nb_vote_received = 0
        self._candidate_date = 0
        # We count the number of time we did have been candidate, to change our timeouts, 1/3 will be favored, 2/3 will be with higher values
        self._candidate_nb_times = 0
        
        # and the election turn we have. This will increase the
        # election_timeout when we go in candidate state,
        # and if someone have a bigger election turn, it wons
        self._election_turn = 0
        
        self._interrrupted = False
        
        # FOLLOWER When did our leader ping us to let us know it is still alive
        self._last_leader_talk_epoch = 0
        
        # DID_VOTE I did send a vote, and I must be sure that I don't let too much time before have a leader
        self._vote_date = 0
        self._vote_for_uuid = None
        
        # Frozen date: I will be frozen for action until this time if I was set as too old
        if FEATURE_FLAG_FROZEN:
            self._end_frozen_date = 0
            self._is_frozen = False
            self._frozen_number = 0  # number of time we did get into frozen state, will increase election turn issue resolution scale
        
        self._creation_date = time.time()
    
    
    def stack_message(self, message):
        with self._pending_messages_lock:
            self._pending_messages.append(message)
    
    
    def _get_nodes_uuids(self):
        return gossiper.get_uuids_of_my_zone_not_off_nodes()
    
    
    # timeouts will change based on the number of elements, as s timing
    def _get_election_timeouts(self):
        ratio = math.ceil(len(self._get_nodes_uuids()) / 100.0)
        low_limit, high_limit = self.ELECTION_TIMEOUT_LIMITS
        return low_limit * 0.001, high_limit * ratio * 0.001
    
    
    def _get_heartbeat_timeout(self):
        ratio = math.ceil(len(self._get_nodes_uuids()) / 100.0)
        return self.HEARTHBEAT_TIMEOUT * ratio * 0.001
    
    
    def stop(self):
        # self._set_state(RAFT_STATES.LEAVED)
        self._interrrupted = True
    
    
    def __str__(self):
        return '(%s:%s)' % (self._uuid, self._state)
    
    
    def _get_print_header(self):
        return '[%3d][%s][%-20s][%.3f]' % (self._election_turn, self._uuid, self._state, time.time() - self._creation_date)
    
    
    def do_print(self, *args, **kwargs):
        logger.info(self._get_print_header(), *args, **kwargs)
    
    
    def _set_state(self, state):
        # Already the same state
        if state == self._state:
            return
        self.do_print("%s => %s " % (self._state, state))
        self._state = state
        
        # Hook test for multiprocess values
        if hasattr(self, 'export_state'):
            states_values = {RAFT_STATES.DID_VOTE: 1, RAFT_STATES.LEADER: 2, RAFT_STATES.FOLLOWER: 3, RAFT_STATES.CANDIDATE: 4, RAFT_STATES.WAIT_FOR_CANDIDATE: 5, RAFT_STATES.LEAVED: 6}
            self.export_state.value = states_values[state]
    
    
    # Send a message to all other nodes, but not me
    def send_to_all_others(self, msg):
        node_uuids = self._get_nodes_uuids()
        # tag the message with current election_turn
        msg['election_turn'] = self._election_turn
        for node_uuid in node_uuids:
            if node_uuid != self._uuid:
                gossiper.send_raft_message(node_uuid, msg)
    
    
    # Return a ok vote to the candidate_uuid node
    def _give_vote_to_candidate(self):
        self.do_print("I give a vote to %s" % (self._vote_for_uuid))
        msg_vote = {'type': RAFT_MESSAGES.VOTE, 'from': self._uuid, 'election_turn': self._election_turn}
        gossiper.send_raft_message(self._vote_for_uuid, msg_vote)
    
    
    # Return a ok vote to the candidate_uuid node
    def _warn_other_node_about_old_election_turn(self, other_uuid):
        m_ret = {'type': RAFT_MESSAGES.WARN_OLD_ELECTION_TURN, 'from': self._uuid, 'election_turn': self._election_turn}
        gossiper.send_raft_message(other_uuid, m_ret)
    
    
    # Wrn all nodes about a new election turn
    def warn_other_nodes_about_old_election_turn(self):
        m_ret = {'type': RAFT_MESSAGES.WARN_OLD_ELECTION_TURN, 'from': self._uuid, 'election_turn': self._election_turn}
        self.send_to_all_others(m_ret)
    
    
    # I did vote for someone, and I want it to win (stable system). So I forward it to other nodes
    def _forward_to_other_nodes_my_candidate(self, msg):
        nodes_uuids = self._get_nodes_uuids()
        n = int(math.ceil(math.log(len(nodes_uuids)))) + 1
        
        n = min(n, len(nodes_uuids))
        
        self.do_print('I did vote for %s and I want to let it know to %s neibours' % (self._vote_for_uuid, n))
        
        # try to find n nodes randomly from nodes
        for i in xrange(n):
            random_other_uuid = random.choice(nodes_uuids)
            gossiper.send_raft_message(random_other_uuid, msg)
    
    
    # someone did ask us to vote for him. We must not already have a leader, and
    # we must be a follower or not already a candidate
    def manage_ask_vote(self, msg):
        if self._leader is None and self._state in [RAFT_STATES.FOLLOWER, RAFT_STATES.WAIT_FOR_CANDIDATE]:  # no leader? ok vote for you guy!
            self._set_state(RAFT_STATES.DID_VOTE)
            self._vote_for_uuid = msg['candidate']
            self._vote_date = time.time()
            self._give_vote_to_candidate()
            # I am helping my new leader to win, I propagate the fact it is a candidate
            self._forward_to_other_nodes_my_candidate(msg)
    
    
    # Someone did vote for me, but I must be a candidate to accept this
    def _manage_vote(self):
        
        if self._state != RAFT_STATES.CANDIDATE:  # exit if not already a candidate
            return
        
        nodes = self._get_nodes_uuids()
        self._nb_vote_received += 1
        quorum_size = math.ceil(float(len(nodes) + 1) / 2)
        # print "I (%d) got a new voter %d" % (n.uuid, self.nb_vote)
        if self._nb_vote_received >= quorum_size:
            self.do_print("did win the vote! with %d votes for me on a total of %d (quorum size=%d) in %.2fs" % (self._nb_vote_received, len(nodes), quorum_size, time.time() - self.start))
            self._set_state(RAFT_STATES.LEADER)
            # warn every one that I am the leader
            m_broad = {'type': RAFT_MESSAGES.LEADER_ELECTED, RAFT_STATES.LEADER: self._uuid, 'from': self._uuid}
            self.send_to_all_others(m_broad)
    
    
    # A new leader is elected, take it
    def _manage_leader_elected(self, m):
        elected_uuid = m['leader']
        if elected_uuid == self._uuid:
            # that's me, I already know about it...
            return
        
        if self._state == RAFT_STATES.LEADER:  # another leader?
            print("TO MANAGE" * 100, self._uuid, elected_uuid, self._term)
            return
        
        # Already know it
        if self._leader is not None and self._leader == elected_uuid:
            self.do_print("Already know about this leader %s" % (elected_uuid))
            return
        
        if self._state in [RAFT_STATES.CANDIDATE, RAFT_STATES.FOLLOWER, RAFT_STATES.DID_VOTE]:  #
            self.do_print("GOT A LEADER JUST ELECTED: %s" % elected_uuid)
            self._leader = elected_uuid
            
            if self._state == RAFT_STATES.CANDIDATE:
                self.do_print(" got a new leader (%s) before me, and I respect it" % (self._leader))
            self._nb_vote_received = 0
            self._set_state(RAFT_STATES.FOLLOWER)
            self._time_to_candidate = 0
            self._last_leader_talk_epoch = time.time()
    
    
    # A new leader is elected, take it
    def _manage_leader_heartbeat(self, msg):
        leader_id = msg['leader']
        if self._leader is None:
            # TODO: get the new leader? only if term is possible of course
            return
        
        if leader_id != self._leader:
            self.do_print("NOT THE GOOD LEADER ASK US? WTF")
            return
        
        if self._state != RAFT_STATES.FOLLOWER:
            self.do_print("A leader ask me to ping but I am not a follower")
            return
        
        # Ok accept this leader ping
        self._last_leader_talk_epoch = time.time()
    
    
    def _look_for_candidated(self):
        if FEATURE_FLAG_FROZEN:
            # if we are frozen, we are not allowed to candidate
            if self._is_frozen:
                return
        
        if time.time() > self._time_to_candidate:
            nodes_uuids = self._get_nodes_uuids()
            self.do_print("is going to be a candidate!")
            self._set_state(RAFT_STATES.CANDIDATE)
            self._nb_vote_received = 1  # I vote for me!
            
            logger.info('NODES: %s' % nodes_uuids)
            possible_voters = nodes_uuids[:]
            random.shuffle(possible_voters)  # so not every one is asking the same on the same time
            ask_vote_msg = {'type': RAFT_MESSAGES.ASK_VOTE, 'candidate': self._uuid, 'from': self._uuid, 'election_turn': self._election_turn}
            for possible_voter_uuid in possible_voters:
                gossiper.send_raft_message(possible_voter_uuid, ask_vote_msg)
            # set that we was a candidate this turn
            self._candidate_nb_times += 1
            self._candidate_date = time.time()  # save when we did candidate, so we know when we are outdated
    
    
    # someone did ask us t ovote for him. We must not already have a leader, and
    # we must be a follower or not already a candidate
    def _launch_heartbeat_to_others(self):
        t0 = time.time()
        msg = {'type': RAFT_MESSAGES.LEADER_HEARTBEAT, 'leader': self._uuid, 'from': self._uuid}
        self.send_to_all_others(msg)
        if (time.time() - t0) > 0.1:
            self.do_print("************ TIME TO LEADER OTHERS: %.3f" % (time.time() - t0))
    
    
    # Launch a dummy message to others, for example to be sure our election_turn is ok
    def launch_dummy_to_random_others(self):
        nodes_uuids = self._get_nodes_uuids()
        n = int(math.ceil(math.log(len(nodes_uuids)))) + 1
        
        if FEATURE_FLAG_FROZEN:
            n *= self.frozen_number  # the more we did get into frozen, the more nodes we try to sync with
        
        n = min(n, len(nodes_uuids))
        
        # try to find n nodes randomly from nodes
        self.do_print("SEND RANDOMLY dummy passage to %s other nodes" % (n))
        msg = {'type': RAFT_MESSAGES.DUMMY, 'election_turn': self._election_turn, 'from': self._uuid}
        for i in xrange(n):
            other_uuid = random.choice(nodes_uuids)
            gossiper.send_raft_message(other_uuid, msg)
    
    
    # We did fail to elect someone, so we increase the election_turn
    # so we will wait more for being candidate.
    # also reset the states
    def _fail_to_elect(self, why):
        self.do_print("We do fail to elect because of: %s. We are increasing the election turn and start a new election." % why)
        self._reset()
        self._election_turn += 1
        self._build_wait_for_candidate_phase()
    
    
    # Get back to default values for vote things :)
    def _reset(self):
        self._nb_vote_received = 0
        self._set_state(RAFT_STATES.FOLLOWER)
        self._time_to_candidate = 0
        self._leader = None
        self._last_leader_talk_epoch = 0
        self._vote_date = 0
        self._vote_for_uuid = None
        self.do_print(" WAS CANDIDATE? %d nb times" % (self._candidate_nb_times))
    
    
    def main(self):
        self._uuid = gossiper.uuid
        # be sure to have a specific random
        random.seed(time.time() * random.random())
        while not self._interrrupted:
            self.node_loop()
            # if self.state not in [RAFT_STATES.DID_VOTE, RAFT_STATES.FOLLOWER]:
            #    print "END Of loop", self.state, self.term
            if self._state == RAFT_STATES.LEADER:
                self.do_print("I AM STILL THE LEADER OF THE TERM", self._term)
                # time.sleep(1)
                continue
            # maybe we are not the leader and so we must look if localy
            # we are ok
            if self._state in [RAFT_STATES.FOLLOWER, RAFT_STATES.CANDIDATE, RAFT_STATES.DID_VOTE]:
                if self._leader is not None:
                    continue
                else:
                    self._fail_to_elect('We still do not have a leader after election turn.')
                    continue
    
    
    def node_loop(self):
        self.start = time.time()
        
        # Start with a build of our future candidate state, so random time is genated to know when we will candidate
        self._build_wait_for_candidate_phase()
        
        while not self._interrrupted:
            msg = None
            wait_time = 1  # if no message, wait a lot
            with self._pending_messages_lock:
                if len(self._pending_messages) >= 1:
                    msg = self._pending_messages.pop()
                    wait_time = 0.001
            
            if FEATURE_FLAG_FROZEN:
                # Look if we are still frozen
                now = time.time()
                if self._end_frozen_date != 0 and now > self._end_frozen_date:
                    self._end_frozen_date = 0
                    self._is_frozen = False
                    self.do_print("Exiting from freeze")
            
            # We have some break in message, so we are not in a huge cluster. If so, maybe we are too small to allow raft
            # to run?
            # PERF: I do it only here and not at each turn to not ask all nodes every loop
            if msg is None:
                # Maybe there is too few nodes in the zone to allow RAFT
                nb_nodes = len(self._get_nodes_uuids())
                if nb_nodes < RAFT_MINIMAL_MEMBERS_NB:
                    time.sleep(wait_time)
                    continue
            
            if msg:
                logger.info('Receiving a message: %s' % str(msg))
                # print " %d I got a message: %s" % (n.uuid, m)
                election_turn = msg['election_turn']
                msg_type = msg['type']
                # if we are over election turn,
                if self._election_turn > election_turn:
                    # I warn the other nodes that the election turn can be too old, and our is %s, other is %d" % (self.uuid, self.election_turn, election_turn)
                    self._warn_other_node_about_old_election_turn(msg['from'])
                    continue
                
                did_change_election_turn = False
                # Maybe the message is from a newer turn than ourselve, if so, close ourself, and accept the new message
                if self._election_turn < election_turn:
                    did_change_election_turn = True
                    self.do_print('We receive an increasing election turn (%d=>%d) from a message type %s' % (self._election_turn, election_turn, msg['type']))
                    
                    if FEATURE_FLAG_FROZEN:
                        # Ok I was too old, go in frozen mode
                        self.is_frozen = True
                        self.frozen_number += 1
                        self.end_frozen_date = time.time() + random.random() * 5 * self.frozen_number  # frozen for ~10s
                        self.do_print("Going to freeze for %ss" % (self.end_frozen_date - time.time()))
                    
                    # action can be different based on if we already did action or not
                    if self._state == RAFT_STATES.FOLLOWER or self._state == RAFT_STATES.WAIT_FOR_CANDIDATE:  # we did nothing, just update our turn without reset timers
                        self._election_turn = election_turn
                    else:  # candidate, leader and did-vote
                        # close our election turn only if we did talk to others, like I am a candidate, a vote or
                        self._fail_to_elect("Our election turn is too old (our=%d other=%d) we close our election turn." % (self._election_turn, election_turn))
                        self._election_turn = election_turn  # get back to this election turn level
                        if self._state == RAFT_STATES.LEADER or self._state == RAFT_STATES.CANDIDATE:
                            # If we did candidate or are leader, warn others about we did fail and do not want their vote any more
                            self.warn_other_nodes_about_old_election_turn()
                    # Randomly ask some others nodes about our election_turn
                    self.launch_dummy_to_random_others()
                
                if did_change_election_turn:
                    self.do_print('I did change election turn and I am still managing message type: %s' % msg['type'])
                
                # someone did warn that its election turn is newer than our, take it
                if msg_type == RAFT_MESSAGES.WARN_OLD_ELECTION_TURN:
                    continue  # was already managed in the previous block, we did invalidate our turn
                
                # Someone ask us for voting for them. We can only if we got no valid leader
                # and we are a follower or not until a candidate
                elif msg_type == RAFT_MESSAGES.ASK_VOTE:
                    self.manage_ask_vote(msg)
                
                elif msg_type == RAFT_MESSAGES.VOTE:  # someone did vote for me?
                    self._manage_vote()
                
                # someone win the match, respect it                                
                elif msg_type == RAFT_MESSAGES.LEADER_ELECTED:
                    self._manage_leader_elected(msg)
                
                # a leader just ping me :)
                elif msg_type == RAFT_MESSAGES.LEADER_HEARTBEAT:
                    self._manage_leader_heartbeat(msg)
                
                # loop as fast as possible to get a new message now
                continue
            
            # print "LOOP", self, "leader", self.leader
            # Heartbeat will be out limit of receiving from others
            hearthbeat_timeout = self._get_heartbeat_timeout()
            
            # If we did-vote, we should look that we should not let time to too much
            # and be sure the election go to the end
            if self._state == RAFT_STATES.DID_VOTE:
                now = time.time()
                if now > self._vote_date + hearthbeat_timeout:
                    self._fail_to_elect("my vote is too old and I don't have any elected leader, I switch back to a new election. exchange timeout=%.3f" % (hearthbeat_timeout))
            
            # If we are a follower witohout a leader, it means we are in the begining of our job
            # and we need to see when we will start to be a candidate
            if self._state == RAFT_STATES.FOLLOWER and self._leader is None:
                self._build_wait_for_candidate_phase()
            
            # if we have a leader and we are a follower, we must look if the leader
            # did talk to us lately. If not, we start a new term
            elif self._state == RAFT_STATES.FOLLOWER and self._leader is not None:
                now = time.time()
                if now > self._last_leader_talk_epoch + hearthbeat_timeout:
                    self._fail_to_elect(" my leader is too old, I refute it. exchange timeout=%.3f" % (hearthbeat_timeout))
            
            elif self._state == RAFT_STATES.CANDIDATE:
                now = time.time()
                if now > self._candidate_date + hearthbeat_timeout:
                    self._fail_to_elect("my candidate was too old (timeout=%s) an I am not a leader (vote=%s) so I swith to a new election" % (hearthbeat_timeout, self._nb_vote_received))
            
            elif self._state == RAFT_STATES.WAIT_FOR_CANDIDATE:
                self._look_for_candidated()
            
            # If I am the leader, we ping other so we respect us
            elif self._state == RAFT_STATES.LEADER:
                self._launch_heartbeat_to_others()
            
            time.sleep(wait_time)
    
    
    def _build_wait_for_candidate_phase(self):
        low_election_timeout, high_election_timout = self._get_election_timeouts()
        
        candidate_race_ratio = 1.0  # by default don't change timeouts
        # Crush 1/3 of the candidates
        if self._candidate_nb_times > 0:
            lucky_number = random.random()
            self.do_print("Current candidate nb times: %d, lucky_number=%.2f" % (self._candidate_nb_times, lucky_number))
            if lucky_number > 0.1:
                self._candidate_nb_times = 0
        
        # Other 2/3 have 3 more time to participate
        if self._candidate_nb_times > 0:
            candidate_race_ratio = 999
            self.do_print("We give a favor to candidature %s %s" % (low_election_timeout, high_election_timout))
        low_election_timeout /= candidate_race_ratio
        high_election_timout /= candidate_race_ratio
        if candidate_race_ratio != 1:
            self.do_print("New timings:%s %s" % (low_election_timeout, high_election_timout))
        
        # ask for a timeout between 150 and 300ms (by default, time can grow up if election fail again and again)
        election_timeout = low_election_timeout + random.random() * (high_election_timout - low_election_timeout)
        self.do_print("Election timeout: %.3f" % (election_timeout))
        self._time_to_candidate = time.time() + election_timeout
        self._set_state(RAFT_STATES.WAIT_FOR_CANDIDATE)


N = 3


# nodes = [{'node': RaftNode(uuid), 'queue': Queue()} for uuid in range(N)]
# nodes = [{'node': RaftNode(uuid), 'queue': [], 'lck': threading.RLock()} for uuid in range(N)]


# def do_the_job(LOOP):
#     # nodes = [{'node':RaftNode(uuid), 'queue': Queue()} for uuid in range(N)]
#
#     threads = []
#     for d in nodes:
#         n = d['node']
#         q = d['queue']
#         t = threading.Thread(None, target=n.main, name='node-%d' % n.uuid, args=(q, nodes))
#         t.daemon = True
#         t.start()
#         threads.append(t)
#
#     for t in threads:
#         t.join()
#
#     # did we got a leader?
#     print("RESULT FOR", LOOP)
#     leader = None
#     max_vote = 0
#     for d in nodes:
#         n = d['node']
#         max_vote = max(max_vote, n.nb_vote)
#         if n.state == RAFT_STATES.LEADER:
#             if leader is not None:
#                 print("WE GOT 2 LEADER, WTF DID YOU DID JEAN?????")
#                 sys.exit("JEAN HOW CAN YOU BREAK SUCH AN ALGO?")
#
#             print("GOT A LEADER", n.uuid, 'with ', n.nb_vote, "LOOP", LOOP)
#             leader = n
#
#     print("Candidate density::", LOOP, 300 * (2 ** LOOP) / float(N), "ms", "& number of candidate in this loop (%d)" % LOOP, len([d for d in nodes if d['node'].state in (RAFT_STATES.CANDIDATE, RAFT_STATES.LEADER)]))
#     if leader is not None:
#         print("Good job jim", "LOOP", LOOP)
#         sys.exit(0)
#
#     print("No leader, max vote is", max_vote)


class RaftManager(BaseManager):
    history_directory_suffix = 'raft'
    
    
    def __init__(self):
        super(RaftManager, self).__init__()
        self.logger = logger
        self.raft_node = RaftNode()
        self.export_http()
    
    
    def do_raft_thread(self):
        self.raft_node.main()
    
    
    def stack_message(self, message, addr_from):
        self.raft_node.stack_message(message)
    
    
    ############## Http interface
    # We must create http callbacks in running because
    # we must have the self object
    def export_http(self):
        @http_export('/raft/state')
        def get_state():
            nb_nodes = len(self.raft_node._get_nodes_uuids())
            current_state = self.raft_node._state
            leader_uuid = self.raft_node._leader
            # when we are leader, the leader uuid is missing
            if current_state == RAFT_STATES.LEADER:
                leader_uuid = gossiper.uuid
            if leader_uuid:
                leader = gossiper.nodes.get(leader_uuid, None)
            else:
                leader = None
            
            return jsoner.dumps({'state': current_state, 'leader': leader, 'nb_nodes': nb_nodes})


rafter = RaftManager()
