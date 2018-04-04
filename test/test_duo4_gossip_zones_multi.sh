#!/usr/bin/env bash

. test/common_shell_functions.sh

NODE_NB=$1

show_my_system_ip


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
    opsbro detectors wait-group 'zone::lan'
fi

if [ "$NODE_NB" == "2" ]; then
    opsbro agent parameters set proxy-node false
    opsbro agent parameters set node-zone  lan
    /etc/init.d/opsbro start
    opsbro detectors wait-group 'zone::lan'
fi

if [ "$NODE_NB" == "3" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set node-zone  internet
    /etc/init.d/opsbro start
    opsbro detectors wait-group 'zone::internet'
fi

if [ "$NODE_NB" == "4" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set node-zone  customer-1
    /etc/init.d/opsbro start
    opsbro detectors wait-group 'zone::customer-1'
fi


opsbro gossip members --detail


# Join all together
opsbro gossip join 172.17.0.2
opsbro gossip join 172.17.0.3
opsbro gossip join 172.17.0.4
opsbro gossip join 172.17.0.5




sleep 2

opsbro gossip zone list
opsbro gossip members --detail



function assert_member {
   NAME="$1"
   ZONE="$2"
   opsbro gossip members | grep 'docker-container' | grep "$NAME" | grep "zone::$ZONE" > /dev/null
   if [ $? != 0 ];then
      echo "ERROR: there should be $NAME in the zone $ZONE"
      opsbro gossip members
      exit 2
   fi
   echo "OK: founded $NAME in $ZONE"
}


function assert_not_member {
   NAME="$1"
   opsbro gossip members | grep 'docker-container' | grep "$NAME" > /dev/null
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
# node4 => 1,3,4 (only the proxy of a higer zone)
if [ "$NODE_NB" == "1" ]; then
   assert_member "node-1" "lan"
   assert_member "node-2" "lan"
   assert_member "node-3" "internet"
   assert_member "node-4" "customer-1"
   exit 0
fi


if [ "$NODE_NB" == "2" ]; then
   assert_member "node-1" "lan"
   assert_member "node-2" "lan"
   assert_member "node-3" "internet"
   assert_member "node-4" "customer-1"
   exit 0
fi


if [ "$NODE_NB" == "3" ]; then
   assert_member "node-1" "lan"
   assert_not_member "node-2"
   assert_member "node-3" "internet"
   assert_member "node-4" "customer-1"
   exit 0
fi


if [ "$NODE_NB" == "4" ]; then
   assert_member "node-1" "lan"
   assert_not_member "node-2"
   assert_member "node-3" "internet"
   assert_member "node-4" "customer-1"
   exit 0
fi


echo "This node is unexpected..."
exit 2
