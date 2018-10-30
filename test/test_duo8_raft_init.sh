#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

print_header "Initializing"
test/set_network_simulated_type "WAN"

NODE_NB=$1

# Only let the gossip part, so we get light test
set_to_minimal_gossip_core

# Set a valid display name for debug
opsbro agent parameters set display_name "node-$NODE_NB"

print_header "Starting"
/etc/init.d/opsbro start

show_my_system_ip

print_header "Joining"
opsbro gossip detect --auto-join --timeout=15


TOTAL_NUMBER_OF_NODES=5

for ii in `seq 1 $TOTAL_NUMBER_OF_NODES`; do
   wait_member_display_name_with_timeout "node-$ii" 20
done



opsbro gossip events add "NODE$NODE_NB-SYNC"
for ii in `seq 1 $TOTAL_NUMBER_OF_NODES`; do
   wait_event_with_timeout "NODE$ii-SYNC" 20
done


print_header "Raft TEST"


opsbro raft wait-leader --timeout=60

if [ $? != 0 ];then
    echo "ERROR: raft do not have a leader"
    opsbro raft state
    cat /var/log/opsbro/gossip.log
    cat /var/log/opsbro/daemon.log
    cat /var/log/opsbro/raft.log
    cat /var/log/opsbro/crash.log 2> /dev/null
    exit 2
fi

opsbro raft state

print_header "Sync for end"
opsbro gossip events add "END-$NODE_NB"
for ii in `seq 1 $TOTAL_NUMBER_OF_NODES`; do
   wait_event_with_timeout "END-$ii" 20
done


exit_if_no_crash "OK: raft got a leader"