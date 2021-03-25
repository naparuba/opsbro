#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

CASE=$1

print_header "Set slow wan"

test/set_network_simulated_type "WAN"

# If node2: wait and quite

# We only want to test gossip here
set_to_minimal_gossip_core

# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"

# We set the node1 as proxy as we want to test the auto-boot discovery part, so we need at least one stable node
if [ $CASE == "NODE1" ]; then
   opsbro agent parameters set proxy-node true
fi

print_header "Start daemon in auto detect mode"
/etc/init.d/opsbro --auto-detect start

if [ $CASE == "NODE2" ]; then
   print_header "Case node2, just waiting for the other node to join us then exit"
   ip addr show
   # Wait for 2 nodes
   print_header "Wait for NODE1 in members"
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

   # Let the history beeing written
   sleep 5

   print_header "Check history"
   HISTORY=$(opsbro gossip history)
   echo "$HISTORY" | grep NODE1
   if [ $? != 0 ]; then
      echo "ERROR: no NODE1 entry in the gossip history"
      echo "$HISTORY"
      cat /var/log/opsbro/daemon.log
      cat /var/log/opsbro/gossip.log
      cat /var/log/opsbro/crash.log 2>/dev/null
      exit 2
   fi

   print_header "Send EVENT and wait for end"
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

   exit_if_no_crash "NODE2 is OK"
fi

print_header "Case 1: try to detect and join other node"

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

# Let the history beeing written
sleep 5

print_header "Check history"
HISTORY=$(opsbro gossip history)
echo "$HISTORY" | grep NODE2
if [ $? != 0 ]; then
   echo "ERROR: no NODE2 entry in the gossip history"
   echo "$HISTORY"
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/gossip.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   exit 2
fi

print_header "Send EVENT and wait for end"
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

exit_if_no_crash "Auto join is OK"
