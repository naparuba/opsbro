#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Set parameters"

test/set_network_simulated_type "WAN"

NODE_NB=$1

# We only want to test gossip here
set_to_only_gossip_and_config_automation

# Set a valid display name for debug
opsbro agent parameters set display_name "node-$NODE_NB"

# File that will be read by the exec commands
echo "FILE FROM node-$NODE_NB" >/tmp/name

# Nodes need to have a KV server
if [ "$NODE_NB" == "1" ]; then
   opsbro agent parameters add groups kv
fi

# Node 2: both & only2
# Node 3: only both
if [ "$NODE_NB" == "2" ]; then
   opsbro agent parameters add groups both
   opsbro agent parameters add groups only2
fi

if [ "$NODE_NB" == "3" ]; then
   opsbro agent parameters add groups both
fi

print_header "Starting & sync"
/etc/init.d/opsbro start

# Wait for other dockers to be spawned
sleep 10

############# Let the two nodes joins
launch_discovery_auto_join

#########  Are the two nodes connected?
wait_member_display_name_with_timeout "node-1" 60
wait_member_display_name_with_timeout "node-2" 60
wait_member_display_name_with_timeout "node-3" 60

opsbro gossip events add "node-$NODE_NB-SYNC"
wait_event_with_timeout 'node-1-SYNC' 20
wait_event_with_timeout 'node-2-SYNC' 20
wait_event_with_timeout 'node-3-SYNC' 20

print_header "Start to test executor"

# Node 2 and 3 will be set in a common group, and one different
# Node1 will try to execute commands based on theses 2 groups
# and will see if one/both execution will succeed

opsbro gossip members

if [ "$NODE_NB" == "1" ]; then
   print_header "Execute on both"

   out_both=$(opsbro executors exec both "/bin/cat /tmp/name")
   if [ $? != 0 ]; then
      echo "ERROR: cannot launch execution for group both $out_both"
      cat /var/log/opsbro/daemon.log
      cat /var/log/opsbro/crash.log
      cat /var/log/opsbro/http_errors.log
      cat /var/log/opsbro/executer.log
      exit 2
   fi

   echo "$out_both" | grep "FILE FROM node-2"
   if [ $? != 0 ]; then
      echo "ERROR: cannot find the node-2 on the execution: $out_both"
      cat /var/log/opsbro/daemon.log
      cat /var/log/opsbro/crash.log
      cat /var/log/opsbro/http_errors.log
      cat /var/log/opsbro/executer.log
      exit 2
   fi
   echo "OK: found node-2"

   echo "$out_both" | grep "FILE FROM node-3"
   if [ $? != 0 ]; then
      echo "ERROR: cannot find the node-3 on the execution: $out_both"
      cat /var/log/opsbro/daemon.log
      cat /var/log/opsbro/crash.log
      cat /var/log/opsbro/http_errors.log
      cat /var/log/opsbro/executer.log
      exit 2
   fi
   echo "OK: found node-3"

   print_header "Execute on only2"
   out_only2=$(opsbro executors exec only2 "/bin/cat /tmp/name")
   if [ $? != 0 ]; then
      echo "ERROR: cannot launch execution for group only2"
      cat /var/log/opsbro/daemon.log
      cat /var/log/opsbro/crash.log
      cat /var/log/opsbro/http_errors.log
      cat /var/log/opsbro/executer.log
      exit 2
   fi

   echo "$out_only2" | grep "FILE FROM node-2"
   if [ $? != 0 ]; then
      echo "ERROR: cannot find the node-2 on the execution: $out_only2"
      exit 2
   fi
   echo "OK: found node-2"

   echo "$out_only2" | grep "FILE FROM node-3"
   if [ $? == 0 ]; then
      echo "ERROR: did find the node-3 on the execution: $out_only2"
      cat /var/log/opsbro/daemon.log
      cat /var/log/opsbro/crash.log
      cat /var/log/opsbro/http_errors.log
      cat /var/log/opsbro/executer.log
      exit 2
   fi
   echo "OK: DID NOT FOUND found node-3"
fi

print_header "Sync for the end"

sleep 10

cat /var/log/opsbro/http_errors.log
cat /var/log/opsbro/executer.log

opsbro gossip events add "node-$NODE_NB-END"
wait_event_with_timeout 'node-1-END' 30
wait_event_with_timeout 'node-2-END' 30
wait_event_with_timeout 'node-3-END' 30


sleep 30
exit_if_no_crash "node-$NODE_NB is exiting well"
