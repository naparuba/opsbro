#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Dumping node info"

echo "Hostname:"
hostname
hostname -I

echo "/etc/hosts"
cat /etc/hosts

echo "Ips:"
show_my_system_ip

echo "Python:"
python --version

echo "Ping"
ping -c 1 node1

more /root/.ssh/*

ls -thor /var/lib/opsbro

INSTALLATION_SOURCE=/var/lib/opsbro/installation-source.tar.gz

if [ ! -f /var/lib/opsbro/installation-source.tar.gz ]; then
    echo "ERROR: there is no installation source available at $INSTALLATION_SOURCE"
    exit 2
fi


print_header "Start our node 1 agent"
/etc/init.d/opsbro start


print_header "Wait for node 2 to be alive (by ssh)"
test_nb=0
while true; do
   if [ $test_nb -gt 10 ]; then
      echo "NODE2 seems to be down, exiting"
      exit 2
   fi
   echo "TEST for node2: $test_nb"
   ping -c 1 node2
   ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no node2 "touch /tmp/node1_is_here"
   if [ $? == 0 ]; then
      echo "node2 is up"
      break
   fi
   let test_nb++
   sleep 1
done

# Set a valid display name for debug
opsbro agent parameters set display_name "node-1"

print_header "Deploy node2"
opsbro deploy new node2

print_header "Wait for node-2 to show"
wait_member_display_name_with_timeout  "node-2"  30

print_header "Wait for event from node2"
opsbro gossip events add "NODE1-DID-SEE-NODE2"
wait_event_with_timeout 'NODE1-DID-SEE-NODE2' 20
wait_event_with_timeout 'NODE2-DID-SEE-NODE1' 20


exit_if_no_crash "Distant installation to node-2 was OK"

