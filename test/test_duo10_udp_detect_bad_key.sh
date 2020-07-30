#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

CASE=$1

print_header "Set slow wan"

test/set_network_simulated_type "WAN"

# If node2: wait and quite


# We only want to test gossip here
set_to_minimal_gossip_core


# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"

/etc/init.d/opsbro start

print_header "Start auto detect"

launch_discovery_auto_join_allow_error


if [ $CASE == "NODE2" ]; then
    print_header "Case node2, check that the other node is NOT here"
    ip addr show
    opsbro gossip wait-members --display-name "NODE1" --timeout 30
    if [ $? == 0 ]; then
       echo "ERROR: NODE1 is present and should NOT"
       cat /var/log/opsbro/daemon.log
       cat /var/log/opsbro/gossip.log
       cat /var/log/opsbro/crash.log 2>/dev/null
       exit 2
    fi
    exit_if_no_crash "NODE2 is alone, do not see node 1"
fi

if [ $CASE == "NODE1" ]; then
    print_header "Case node1, check that the other node is NOT here"
    ip addr show
    opsbro gossip wait-members --display-name "NODE2" --timeout 30
    if [ $? == 0 ]; then
       echo "ERROR: NODE2 is present and should NOT"
       cat /var/log/opsbro/daemon.log
       cat /var/log/opsbro/gossip.log
       cat /var/log/opsbro/crash.log 2>/dev/null
       exit 2
    fi
    exit_if_no_crash "NODE1 is alone, do not see node 1"
fi


echo "ERROR: unknown node"
exit 2