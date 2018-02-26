#!/usr/bin/env bash

CASE=$1

# If node2: wait and quite

if [ $CASE == "NODE2" ]; then
    echo "Case node2, just waiting for the other node to join us then exit"
    ip addr show
    sleep 60
    cat /var/log/opsbro/gossip.log
    exit 1
fi

# Case 1: try to detect and join other node

# Sleep a bit to be sure that node2 is up and ready to answer us
#sleep 120

opsbro gossip detect --auto-join
cat /var/log/opsbro/gossip.log

NB_MEMBERS=$(opsbro gossip members | grep 'docker-container' | wc -l)

if [ $NB_MEMBERS != 2 ]; then
   echo "BAD number of members: $NB_MEMBERS"

   exit 2
fi

opsbro gossip members

echo "Auto join is OK"


