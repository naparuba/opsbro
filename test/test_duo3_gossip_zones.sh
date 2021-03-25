#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

test/set_network_simulated_type "WAN"

NODE_NB=$1

show_my_system_ip

# Do not enable monitoring & configuration stuff here
set_to_only_gossip_and_detection

# Set a valid display name for debug
opsbro agent parameters set display_name "node-$NODE_NB"

# 1: internet and proxy
# 2: internet NOT proxy
# 3: lan & proxy
# 4: lan & NOT proxy
if [ "$NODE_NB" == "1" ]; then
   opsbro agent parameters set proxy-node true
   opsbro agent parameters set zone internet
   /etc/init.d/opsbro start
   opsbro detectors wait-group 'zone::internet'
fi

if [ "$NODE_NB" == "2" ]; then
   opsbro agent parameters set proxy-node false
   opsbro agent parameters set zone internet
   /etc/init.d/opsbro start
   opsbro detectors wait-group 'zone::internet'
fi

if [ "$NODE_NB" == "3" ]; then
   opsbro agent parameters set proxy-node true
   opsbro agent parameters set zone lan
   /etc/init.d/opsbro start
   opsbro detectors wait-group 'zone::lan'
fi

if [ "$NODE_NB" == "4" ]; then
   opsbro agent parameters set proxy-node false
   opsbro agent parameters set zone lan
   /etc/init.d/opsbro start
   opsbro detectors wait-group 'zone::lan'
fi

opsbro gossip members --detail

# Join all together
opsbro gossip join node1
opsbro gossip join node2
opsbro gossip join node3
opsbro gossip join node4

assert_no_crash

sleep 2

opsbro gossip zone list
opsbro gossip members --detail

function assert_member() {
   NAME="$1"
   ZONE="$2"
   opsbro gossip members | grep "$NAME" | grep "zone::$ZONE" >/dev/null
   if [ $? != 0 ]; then
      echo "ERROR: there should be $NAME in the zone $ZONE"
      opsbro gossip members
      exit 2
   fi
   echo "OK: founded $NAME in $ZONE"
}

function assert_not_member() {
   NAME="$1"
   opsbro gossip members | grep "$NAME" >/dev/null
   if [ $? == 0 ]; then
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
# node4 => 1,3,4 (only the proxy of a higer zone)
if [ "$NODE_NB" == "1" ]; then
   assert_member "node-1" "internet"
   assert_member "node-2" "internet"
   assert_member "node-3" "lan"
   assert_member "node-4" "lan"
   exit_if_no_crash "Node 1 exit"
fi

if [ "$NODE_NB" == "2" ]; then
   assert_member "node-1" "internet"
   assert_member "node-2" "internet"
   assert_member "node-3" "lan"
   assert_member "node-4" "lan"
   exit_if_no_crash "Node 2 exit"
fi

if [ "$NODE_NB" == "3" ]; then
   assert_member "node-1" "internet"
   assert_not_member "node-2"
   assert_member "node-3" "lan"
   assert_member "node-4" "lan"
   exit_if_no_crash "Node 3 exit"
fi

if [ "$NODE_NB" == "4" ]; then
   assert_member "node-1" "internet"
   assert_not_member "node-2"
   assert_member "node-3" "lan"
   assert_member "node-4" "lan"
   exit_if_no_crash "Node 4 exit"
fi

echo "This node is unexpected..."
exit 2
