#!/usr/bin/env bash

NODE_NB=$1

# Set a valid display name for debug
opsbro agent parameters set display_name "node-$NODE_NB"

/etc/init.d/opsbro start

# Wait for other dockers to be spawned
sleep 10


ip addr show | grep eth0


# Node 1 ip=2
if [ "$NODE_NB" == "1" ]; then
  opsbro gossip join 172.17.0.3
  opsbro gossip join 172.17.0.4
fi

# Node 2 ip=3
if [ "$NODE_NB" == "2" ]; then
  opsbro gossip join 172.17.0.2
  opsbro gossip join 172.17.0.4
fi


# Node 3 ip=4
if [ "$NODE_NB" == "3" ]; then
  opsbro gossip join 172.17.0.2
  opsbro gossip join 172.17.0.3
fi

sleep 20
echo "Waiting done, everyone should be there"



opsbro gossip wait-members --display-name "node-1" --timeout 10
if [ $? != 0 ]; then
   echo "ERROR: node-1 is not present after 60s"
   opsbro gossip members --detail
   exit 2
fi
opsbro gossip wait-members --display-name "node-2" --timeout 10
if [ $? != 0 ]; then
   echo "ERROR: node-2 is not present after 60s"
   opsbro gossip members --detail
   exit 2
fi
opsbro gossip wait-members --display-name "node-3" --timeout 10
if [ $? != 0 ]; then
   echo "ERROR: node-3 is not present after 60s"
   opsbro gossip members --detail
   exit 2
fi



# NODE1: fast exit
# NODE2: ask leave
# NODE3: look for dead & leaved node
if [ "$NODE_NB" == "1" ]; then
   # let the others finish
   /etc/init.d/opsbro stop
   cat /var/log/opsbro/gossip.log
   #cat /var/log/opsbro/daemon.log
   echo "NODE1 is exiting and nothing more to check for it, it will be dead"
   exit 0
fi


if [ "$NODE_NB" == "2" ]; then
   sleep 10
   opsbro gossip leave
   opsbro gossip members --detail
   # Node: leave will wait 10s before exit daemon, so we should not kill the
   # docker instance directly
   sleep 20
   cat /var/log/opsbro/gossip.log
   #cat /var/log/opsbro/daemon.log
   echo "NODE2 will be detected as leaved from node 3"
   exit 0
fi


function assert_count {
   NB=$(opsbro gossip members | grep 'docker-container' | grep "$1" | wc -l)
   if [ "$NB" != "$2" ]; then
      echo "ERROR: there should be $2 $1 but there are $NB"
      opsbro gossip members
      exit 2
   fi
   echo "OK: founded $NB $2 nodes"
}

if [ "$NODE_NB" == "3" ]; then
   sleep 30
   cat /var/log/opsbro/gossip.log
   opsbro gossip members --detail

   # THERE should be
   # * one alive (node3)
   # * one dead (node1)
   # * one leave (node2)
   assert_count "alive" "1"
   assert_count "dead" "1"
   assert_count "leave" "1"

   echo "All states are good, exiting"

   cat /var/lib/opsbro/nodes_history/*

   exit 0
fi

echo "This node is unexpected..."
exit 2
