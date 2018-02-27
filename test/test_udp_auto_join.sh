#!/usr/bin/env bash

CASE=$1

# If node2: wait and quite

if [ $CASE == "NODE2" ]; then
    echo "Case node2, just waiting for the other node to join us then exit"
    ip addr show
    sleep 60
    printf "Node2 gossip view\n"
    opsbro gossip members
    printf "Node 2 logs:\n"
    cat /var/log/opsbro/gossip.log
    exit 0
fi

# Case 1: try to detect and join other node

# Sleep a bit to be sure that node2 is up and ready to answer us
#sleep 120
ip addr show

opsbro gossip detect --auto-join

opsbro gossip members
NB_MEMBERS=$(opsbro gossip members | grep 'docker-container' | wc -l)

if [ $NB_MEMBERS != 2 ]; then
   echo "BAD number of members: $NB_MEMBERS"
   cat /var/log/opsbro/gossip.log
   exit 2
fi



echo "Auto join is OK"


