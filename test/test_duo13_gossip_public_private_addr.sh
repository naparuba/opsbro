#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

test/set_network_simulated_type "WAN"

NODE_NB=$1

# We only want to test gossip here
set_to_minimal_gossip_core

hostname -I

show_my_system_ip

python --version

# Set a valid display name for debug
opsbro agent parameters set display_name "node-$NODE_NB"




# NODE:
# 1 & 2 : higher zone, exchange with private addr
# 3: lower zone, exchange with public addr

if [ "$NODE_NB" == "1" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set zone  lan
    /etc/init.d/opsbro start
    assert_group 'zone::lan'
fi

if [ "$NODE_NB" == "2" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set zone  lan
    /etc/init.d/opsbro start
    assert_group 'zone::lan'
fi

if [ "$NODE_NB" == "3" ]; then
    opsbro agent parameters set proxy-node true
    opsbro agent parameters set zone  internet
    /etc/init.d/opsbro start
    assert_group 'zone::internet'
fi

opsbro gossip detect --auto-join --timeout=15

opsbro gossip members

opsbro agent info

opsbro agent print local-addr
opsbro agent print public-addr

assert_no_crash

print_header "Waiting done, everyone should be there"


wait_member_display_name_with_timeout "node-1" 10
wait_member_display_name_with_timeout "node-2" 10
wait_member_display_name_with_timeout "node-3" 10


# node-1: see node-2 as private addr, node-3 as public
# node-2: see node-1 as private addr, node-3 as public
# node-1: see node-1 & node-2 as public
print_header "Checking valid addr detected"

if [ "$NODE_NB" == "1" ]; then
   # Check MY addr
   assert_public_addr_range "$OPSBRO_PUBLIC_NETWORK"
   assert_local_addr_range "$OPSBRO_LOCAL_NETWORK"

   # And the others
   addr2=$(get_other_node_addr "node-2")
   echo "NODE2: $addr2 Should be in local network $OPSBRO_LOCAL_NETWORK"
   assert_addr_in_range "$addr2"  "$OPSBRO_LOCAL_NETWORK"

   addr3=$(get_other_node_addr "node-3")
   echo "NODE3: $addr3 Should be in public network $OPSBRO_PUBLIC_NETWORK"
   assert_addr_in_range "$addr3"  "$OPSBRO_PUBLIC_NETWORK"


   exit_if_no_crash "NODE1 is OK"
fi

if [ "$NODE_NB" == "2" ]; then
   # Check MY addr
   assert_public_addr_range "$OPSBRO_PUBLIC_NETWORK"
   assert_local_addr_range "$OPSBRO_LOCAL_NETWORK"

   # And the others
   addr1=$(get_other_node_addr "node-1")
   echo "NODE1: $addr1 Should be in local network $OPSBRO_LOCAL_NETWORK"
   assert_addr_in_range "$addr1"  "$OPSBRO_LOCAL_NETWORK"

   addr3=$(get_other_node_addr "node-3")
   echo "NODE3: $addr3 Should be in public network $OPSBRO_PUBLIC_NETWORK"
   assert_addr_in_range "$addr3"  "$OPSBRO_PUBLIC_NETWORK"

   exit_if_no_crash "NODE2 is OK"
fi


if [ "$NODE_NB" == "3" ]; then
   # Check MY addr
   assert_public_addr_range "$OPSBRO_PUBLIC_NETWORK"
   assert_local_addr_range "$OPSBRO_PUBLIC_NETWORK"   # no local for this one

   # And the others
   addr1=$(get_other_node_addr "node-1")
   echo "NODE1: $addr1 Should be in public network $OPSBRO_PUBLIC_NETWORK"
   assert_addr_in_range "$addr1"  "$OPSBRO_PUBLIC_NETWORK"

   addr2=$(get_other_node_addr "node-2")
   echo "NODE2: $addr2 Should be in public network $OPSBRO_PUBLIC_NETWORK"
   assert_addr_in_range "$addr2"  "$OPSBRO_PUBLIC_NETWORK"

   exit_if_no_crash "NODE3 is OK"
fi


echo "This node is unexpected..."
exit 2
