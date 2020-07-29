#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

#test/set_network_simulated_type "WAN"

CASE=$1

# NODE1 => grok various data
# NODE2 => module node, that listen to data and save them in database


show_my_system_ip


# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"


opsbro packs overload global.imrane
opsbro packs parameters set local.imrane.enabled true

if [ "$CASE" == "NODE1" ]; then
   opsbro agent parameters add groups imrane-agregator
fi

if [ "$CASE" == "NODE2" ]; then
   opsbro agent parameters add groups imrane-collector
fi


#assert_can_ping node1
#assert_can_ping node2



/etc/init.d/opsbro start


############# Let the two nodes joins
launch_discovery_auto_join



#########  Are the two nodes connected?
wait_member_display_name_with_timeout "NODE1" 60
wait_member_display_name_with_timeout "NODE2" 60



opsbro gossip events add "BEFORE-TEST-$CASE"
wait_event_with_timeout "BEFORE-TEST-NODE1" 60
wait_event_with_timeout "BEFORE-TEST-NODE2" 60


opsbro gossip members
# There thouls be 2 alive node, not a single suspect
assert_state_count "alive" "2"

ls -thor /var/log/opsbro/

cat /var/log/opsbro/module.imrane.log

############## Database test

# Let the daemon save data
sleep 30

if [ "$CASE" == "NODE1" ]; then
   echo "Looking if database is valid"
   ls -thor /tmp/
   # we must close because we cannot open the database while the other process is on it
   /etc/init.d/opsbro stop
   NB=$(sqlite3 /tmp/agregator.db "select count(*) from Data where KeyName = 'toto';")
   if [ $? != 0 ];then
       echo "ERROR: the database is not valid: $NB"
       ls -thor /tmp
       exit 2
   fi

   echo "OK there are $NB entries in the database"
   /etc/init.d/opsbro start

fi


########## Stoping nodes
opsbro gossip events add "END-$CASE"


wait_event_with_timeout "END-NODE1" 120
wait_event_with_timeout "END-NODE2" 120

sleep 20

exit_if_no_crash "Agregator module test di done"