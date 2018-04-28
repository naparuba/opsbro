#!/usr/bin/env bash

. test/common_shell_functions.sh

test/set_network_simulated_type "WAN"

CASE=$1

# NODE1 => starts and insert a event, check for the event
# NODE2 => starts and check that the event is not present
# JOIN the two nodes, check that the node2 have the node1 event

show_my_system_ip


# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"



/etc/init.d/opsbro start


if [ $CASE == "NODE1" ]; then
   opsbro gossip events add 'EVENT-IN-NODE1'
   wait_event_with_timeout 'EVENT-IN-NODE1' 10
fi


############# Let the two nodes joins
opsbro gossip detect --auto-join --timeout=15

#cat /var/log/opsbro/gossip.log
#cat /var/log/opsbro/daemon.log

#########  Are the two nodes connected?
if [ $CASE == "NODE1" ]; then
   wait_member_display_name_with_timeout "NODE2" 60
fi

if [ $CASE == "NODE2" ]; then
   wait_member_display_name_with_timeout "NODE1" 60
fi


############# NODE2 : should have the node1 event
if [ $CASE == "NODE2" ]; then
    wait_event_with_timeout  'EVENT-IN-NODE1'  10
fi





# Let the two nodes ends in the same time
if [ $CASE == "NODE1" ]; then
   opsbro gossip events add 'NODE1-END'
   # Be sure we are sending it to the other node
   sleep 2
   wait_event_with_timeout  'NODE2-END'  10
fi

if [ $CASE == "NODE2" ]; then
   opsbro gossip events add 'NODE2-END'
   # Be sure we are sending it to the other node
   sleep 2
   wait_event_with_timeout  'NODE1-END'  10
fi


echo "EVENT sharing is done"