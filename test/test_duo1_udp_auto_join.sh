#!/usr/bin/env bash

CASE=$1

test/set_network_simulated_type "WAN"

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
       cat /var/log/opsbro/daemon.log
       cat /var/log/opsbro/gossip.log
       cat /var/log/opsbro/crash.log 2>/dev/null
       exit 2
    fi
    printf "Node2 gossip view\n"
    opsbro gossip members

    # Warn the first node we are done
    opsbro gossip events add 'NODE2-END'
    # Be sure we are sending it to the other node
    sleep 2
    opsbro gossip events wait 'NODE1-END' --timeout=10
    if [ $? != 0 ]; then
       echo "ERROR: NODE1 did not end after after 60s"
       cat /var/log/opsbro/daemon.log
       cat /var/log/opsbro/gossip.log
       cat /var/log/opsbro/crash.log 2>/dev/null
       exit 2
    fi

    echo "NODE2 is OK"
    exit 0
fi

# Case 1: try to detect and join other node

# Sleep a bit to be sure that node2 is up and ready to answer us
ip addr show

opsbro gossip wait-members --display-name "NODE2" --timeout 60


if [ $? != 0 ]; then
   echo "ERROR: cannot find NODE2"
   opsbro gossip members
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/gossip.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   exit 2
fi


# Warn the first node we are done
opsbro gossip events add 'NODE1-END'
# Be sure we are sending it to the other node
sleep 2
opsbro gossip events wait 'NODE2-END' --timeout=10
if [ $? != 0 ]; then
   echo "ERROR: NODE2 did not end after after 60s"
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/gossip.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   exit 2
fi


echo "Auto join is OK"