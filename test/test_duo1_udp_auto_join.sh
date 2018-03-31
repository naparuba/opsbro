#!/usr/bin/env bash

CASE=$1

# If node2: wait and quite

# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"

/etc/init.d/opsbro start

opsbro gossip detect --auto-join --timeout=15

if [ $CASE == "NODE2" ]; then
    echo "Case node2, just waiting for the other node to join us then exit"
    ip addr show
    # Wait for 2 nodes
    opsbro gossip wait-members --display-name "NODE1" --timeout 60
    if [ $? != 0 ]; then
       echo "ERROR: NODE1 is not present after 60s"
       exit 2
    fi
    printf "Node2 gossip view\n"
    opsbro gossip members

    # Let the other node reach us
    sleep 60
    exit 0
fi

# Case 1: try to detect and join other node

# Sleep a bit to be sure that node2 is up and ready to answer us
ip addr show

opsbro gossip wait-members --display-name "NODE2" --timeout 60


if [ $? != 0 ]; then
   echo "ERROR: cannot find NODE2"
   opsbro gossip members
   cat /var/log/opsbro/gossip.log
   exit 2
fi



echo "Auto join is OK"

# Let the other node reach us
sleep 60

