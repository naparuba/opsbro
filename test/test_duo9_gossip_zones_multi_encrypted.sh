#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

test/set_network_simulated_type "WAN"

TOTAL_NUMBER_OF_NODES=4

NODE_NB=$1

show_my_system_ip

# Do not enable monitoring & configuration stuff here
set_to_only_gossip_and_detection

# Set a valid display name for debug
opsbro agent parameters set display_name "node-$NODE_NB"


# LAN > internet > customer-1

# 1: lan and proxy
# 2: lan NOT proxy
# 3: internet & proxy
# 4: customer-1 & proxy
if [ "$NODE_NB" == "1" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set node-zone  lan
    /etc/init.d/opsbro start
    assert_group 'zone::lan'
fi

if [ "$NODE_NB" == "2" ]; then
    opsbro agent parameters set proxy-node false
    opsbro agent parameters set node-zone  lan
    /etc/init.d/opsbro start
    assert_group 'zone::lan'
fi

if [ "$NODE_NB" == "3" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set node-zone  internet
    /etc/init.d/opsbro start
    assert_group 'zone::internet'
fi

if [ "$NODE_NB" == "4" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set node-zone  customer-1
    /etc/init.d/opsbro start
    assert_group 'zone::customer-1'
fi

# If daemon is dead here, we have a problem and exit
assert_no_crash

# all node must have a encrypted zone
assert_my_zone_is_encrypted


opsbro gossip members --detail


# Join all together
opsbro gossip detect --auto-join --timeout=15
if [ $? != 0 ];then
   echo "ERROR: cannot discover any other node in UDP, exiting"
   exit 2
fi
# To be sure that all 4 are linked (maybe the lower node join together and not with the higer one)
opsbro gossip join node1
opsbro gossip join node2
opsbro gossip join node3
opsbro gossip join node4

assert_no_crash


sleep 2

opsbro gossip zone list
opsbro gossip members --detail

#opsbro gossip events add "$MY_NAME-EVENT"


function assert_member {
   NAME="$1"
   ZONE="$2"
   opsbro gossip members | grep "$NAME" | grep "zone::$ZONE" > /dev/null
   if [ $? != 0 ];then
      echo "ERROR: there should be $NAME in the zone $ZONE"
      opsbro gossip members
      exit 2
   fi
   echo "OK: founded $NAME in $ZONE"
}


function assert_not_member {
   NAME="$1"
   opsbro gossip members | grep "$NAME" > /dev/null
   if [ $? == 0 ];then
      echo "ERROR: there should not be $NAME"
      opsbro gossip members
      exit 2
   fi
   echo "OK: not founded $NAME"
}


#WHO SEE WHO?
# node1 => every one
# node2 => every one
# node3 => 1,3,4 (only the proxy of a higer zone)
# node4 => 3,4 (only the proxy of a directly higer zone)
if [ "$NODE_NB" == "1" ]; then
   assert_member "node-1" "lan"
   #wait_event_with_timeout "node-1-EVENT" 60
   assert_member "node-2" "lan"
   #wait_event_with_timeout "node-2-EVENT" 60
   # Know about higher realm too
   assert_member "node-3" "internet"
   #wait_event_with_timeout "node-3-EVENT" 60
   assert_member "node-4" "customer-1"
   #wait_event_with_timeout "node-4-EVENT" 60

   # We cannot synchronize end as all nodes are not talking each others
   sleep 20
   exit_if_no_crash "Node 1 exit"
fi

# LAN TOO
if [ "$NODE_NB" == "2" ]; then
   assert_member "node-1" "lan"
   #wait_event_with_timeout "node-1-EVENT" 60

   assert_member "node-2" "lan"
   #wait_event_with_timeout "node-2-EVENT" 60

   assert_member "node-3" "internet"
   #wait_event_with_timeout "node-3-EVENT" 60

   assert_member "node-4" "customer-1"
   #wait_event_with_timeout "node-4-EVENT" 60

   # We cannot synchronize end as all nodes are not talking each others
   sleep 20
   exit_if_no_crash "Node 2 exit"
fi

# node3 internet => 1,3,4 (only the proxy of a higer zone)
if [ "$NODE_NB" == "3" ]; then
   assert_member "node-1" "lan"
   assert_not_member "node-2"
   # Do not have access to higher events

   assert_member "node-3" "internet"
   #wait_event_with_timeout "node-3-EVENT" 60

   assert_member "node-4" "customer-1"
   #wait_event_with_timeout "node-4-EVENT" 60

   sleep 20
   exit_if_no_crash "Node 3 exit"
fi

# node4 customer-1=> 3,4 (only the proxy of a direct higer zone)
if [ "$NODE_NB" == "4" ]; then
   assert_not_member "node-1"
   assert_not_member "node-2"
   assert_member "node-3" "internet"
   # Do not have access to higher events

   assert_member "node-4" "customer-1"
   #wait_event_with_timeout "node-4-EVENT" 60

   sleep 20
   exit_if_no_crash "Node 4 exit"
fi


echo "This node is unexpected..."
exit 2
