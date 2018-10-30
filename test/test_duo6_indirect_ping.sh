#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

test/set_network_simulated_type "WAN"

CASE=$1

# NODE1 => cannot ping 3
# NODE2 => relay node
# NODE3 => cannot ping 1

show_my_system_ip

# We only want to test gossip here
set_to_minimal_gossip_core


# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"


assert_can_ping node1
assert_can_ping node2
assert_can_ping node3




/etc/init.d/opsbro start


############# Let the two nodes joins
opsbro gossip detect --auto-join --timeout=15



#########  Are the two nodes connected?
wait_member_display_name_with_timeout "NODE1" 60
wait_member_display_name_with_timeout "NODE2" 60
wait_member_display_name_with_timeout "NODE3" 60


opsbro gossip events add "BEFORE-TEST-$CASE"
wait_event_with_timeout "BEFORE-TEST-NODE1" 60
wait_event_with_timeout "BEFORE-TEST-NODE2" 60
wait_event_with_timeout "BEFORE-TEST-NODE3" 60

# Now block ping
if [ $CASE == "NODE1" ]; then
   iptables -I INPUT -s node3 -j DROP
   iptables -L
   assert_cannot_ping node3
fi

if [ $CASE == "NODE3" ]; then
   iptables -I INPUT -s node1 -j DROP
   iptables -L
   assert_cannot_ping node1
fi

sleep 30

opsbro gossip members
# There thouls be 3 alive node, not a single suspect
assert_state_count "alive" "3"

cat /var/log/opsbro/gossip.log

# Wait for all nodes to be here because if node2 or node 1 stop before node3, it will not detect 3 alives

# As node2 is the relay, we should finish this last one in last
if [ $CASE == "NODE1" ] || [ $CASE == "NODE3" ]; then
  opsbro gossip events add "END-$CASE"
fi
wait_event_with_timeout "END-NODE1" 60
wait_event_with_timeout "END-NODE3" 60

if [ $CASE == "NODE2" ];then
   opsbro gossip events add "END-$CASE"
fi
wait_event_with_timeout "END-NODE2" 60

sleep 10

exit_if_no_crash "INDIRECT PING is done"