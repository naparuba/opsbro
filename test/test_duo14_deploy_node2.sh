#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Start the node2 ssh server"
# Asap: start the ssh server for node1
/etc/init.d/ssh start

print_header "Dumping node info"

echo "Hostname:"
hostname
hostname -I

echo "/etc/hosts"
cat /etc/hosts

echo "Ips:"
show_my_system_ip

echo "Python:"
$PYTHON_EXE --version

echo "Ping"
ping -c 1 node1
ping -c 1 node2

more /root/.ssh/*

print_header "Waiting for node 1 to connect"
test_nb=0
while true; do
   if [ $test_nb -gt 30 ]; then
      echo "NODE1 did not connect, exiting"
      exit 2
   fi
   echo "TEST for node1 presence: $test_nb"
   ping -c 1 node1
   if [ -f /tmp/node1_is_here ]; then
      echo "node1 just connect, we can continue"
      break
   fi
   let test_nb++
   sleep 1
done


print_header "Waiting for agent to be installed and running"
# Now wait for installation to be done, and agent running
test_nb=0
while true; do
   if [ $test_nb -gt 30 ]; then
      echo "NODE1 did not install us, exiting"
      exit 2
   fi
   echo "TEST for installation from node1: $test_nb"
   opsbro agent info
   if [ $? == 0 ]; then
      echo "Opsbro is now running, we can continue"
      break
   fi
   let test_nb++
   sleep 1
done

print_header "Wait for node1 to be goin in gossip"
wait_member_display_name_with_timeout node-1 30


print_header "Rename ourselve into node-2"
opsbro agent parameters set display_name "node-2"
opsbro gossip members

print_header "INSTALLATION: Wait for event from node1"

opsbro gossip members
# Let the node-1 know we did see it
opsbro gossip events add "NODE2-DID-SEE-NODE1"
wait_event_with_timeout 'NODE1-DID-SEE-NODE2' 20
wait_event_with_timeout 'NODE2-DID-SEE-NODE1' 20



# Now the update
print_header "UPDATE: Wait for event from node1"

opsbro gossip members
# Let the node-1 know we did see it
opsbro gossip events add "NODE2-DID-SEE-NODE1-UPDATE"
wait_event_with_timeout 'NODE1-DID-SEE-NODE2-UPDATE' 20
wait_event_with_timeout 'NODE2-DID-SEE-NODE1-UPDATE' 20


sleep 10  # always sleep a bit to be ok with all events
exit_if_no_crash "Installation + update from node-1 is OK"
