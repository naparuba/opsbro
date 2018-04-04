#!/usr/bin/env bash

CASE=$1

# NODE1 => starts and insert a event, check for the event
# NODE2 => starts and check that the event is not present
# JOIN the two nodes, check that the node2 have the node1 event

ip addr show | grep eth

# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"




/etc/init.d/opsbro start


if [ $CASE == "NODE1" ]; then
   opsbro gossip events add 'EVENT-IN-NODE1'
   opsbro gossip events wait 'EVENT-IN-NODE1' --timeout=10
   if [ $? != 0 ]; then
       echo "ERROR: NODE1 do not have it's own event"
       exit 2
   fi
fi


############# Let the two nodes joins
opsbro gossip detect --auto-join --timeout=15

#cat /var/log/opsbro/gossip.log
#cat /var/log/opsbro/daemon.log

#########  Are the two nodes connected?
if [ $CASE == "NODE1" ]; then
   opsbro gossip wait-members --display-name "NODE1" --timeout 60
   if [ $? != 0 ]; then
       echo "ERROR: NODE1 is not present after 60s"
       exit 2
   fi
fi

if [ $CASE == "NODE2" ]; then
   opsbro gossip wait-members --display-name "NODE2" --timeout 60
   if [ $? != 0 ]; then
       echo "ERROR: NODE2 is not present after 60s"
       exit 2
   fi
fi


############# NODE2 : should have the node1 event
if [ $CASE == "NODE2" ]; then
    opsbro gossip events wait 'EVENT-IN-NODE1' --timeout=10
    if [ $? != 0 ]; then
       echo "ERROR: NODE2 do not have the node1 event"
       exit 2
   fi
fi





# Let the two nodes ends in the same time
if [ $CASE == "NODE1" ]; then
   opsbro gossip events add 'NODE1-END'
   # Be sure we are sending it to the other node
   sleep 2
   opsbro gossip events wait 'NODE2-END' --timeout=10
   if [ $? != 0 ]; then
      echo "ERROR: NODE2 did not end after after 60s"
      cat /var/log/opsbro/gossip.log
      exit 2
   fi
fi

if [ $CASE == "NODE2" ]; then
   opsbro gossip events add 'NODE2-END'
   # Be sure we are sending it to the other node
   sleep 2
   opsbro gossip events wait 'NODE1-END' --timeout=10
   if [ $? != 0 ]; then
      echo "ERROR: NODE1 did not end after after 60s"
      cat /var/log/opsbro/gossip.log
      exit 2
   fi
fi


echo "EVENT sharing is done"