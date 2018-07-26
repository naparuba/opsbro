#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

test/set_network_simulated_type "WAN"

NODE_NB=$1

# Set a valid display name for debug
opsbro agent parameters set display_name "node-$NODE_NB"

/etc/init.d/opsbro start

# Wait for other dockers to be spawned
sleep 10


show_my_system_ip

# Thanks docker compose for DNS resolution
# Node 1 ip=2
if [ "$NODE_NB" == "1" ]; then
  opsbro gossip join node2
  opsbro gossip join node3
fi

# Node 2 ip=3
if [ "$NODE_NB" == "2" ]; then
  opsbro gossip join node1
  opsbro gossip join node3
fi


# Node 3 ip=4
if [ "$NODE_NB" == "3" ]; then
  opsbro gossip join node1
  opsbro gossip join node2
fi

sleep 20
print_header "Waiting done, everyone should be there"


wait_member_display_name_with_timeout "node-1" 10
wait_member_display_name_with_timeout "node-2" 10
wait_member_display_name_with_timeout "node-3" 10


opsbro gossip events add "NODE$NODE_NB-SYNC"
wait_event_with_timeout 'NODE1-SYNC' 20
wait_event_with_timeout 'NODE2-SYNC' 20
wait_event_with_timeout 'NODE3-SYNC' 20


# NODE1: fast exit
# NODE2: ask leave
# NODE3: look for dead & leaved node
if [ "$NODE_NB" == "1" ]; then
   # let the others finish
   /etc/init.d/opsbro stop
   echo "NODE1 is exiting and nothing more to check for it, it will be dead"
   exit 0
fi


if [ "$NODE_NB" == "2" ]; then
   #sleep 10
   opsbro gossip events add 'NODE2-LEAVING'
   wait_event_with_timeout 'NODE3-RECEIVE-LEAVING' 20

   opsbro gossip leave
   opsbro gossip members --detail
   # Node: leave will wait 10s before exit daemon, so we should not kill the
   # docker instance directly

   echo "Sleeping until the node3 receive our leave"
   sleep 20
   cat /var/log/opsbro/gossip.log
   echo "NODE2 exiting"
   opsbro gossip history
   exit 0
fi


if [ "$NODE_NB" == "3" ]; then
   # wait until the node2 is ready to leave
   wait_event_with_timeout 'NODE2-LEAVING' 20
   # Le tthe node 2 know we receive, so it can leave and wait for us to exit
   opsbro gossip events add 'NODE3-RECEIVE-LEAVING'

   echo "Wait until we receive gossip messages from node2"

   cat /var/log/opsbro/gossip.log
   opsbro gossip members

   # THERE should be
   # * one leave (node2)
   # * one dead (node1)
   # * one alive (node3)
   # NOTE: tryto detect from the most ephemerus  state to the most stable one
   assert_state_count "leave" "1"
   assert_state_count "dead" "1"
   assert_state_count "alive" "1"


   echo "NODE3: All states are good, exiting"
   cat /var/log/opsbro/gossip.log
   exit 0
fi

echo "This node is unexpected..."
exit 2
