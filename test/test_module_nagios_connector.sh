#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test Nagios export (dummy check)"

/etc/init.d/opsbro start

opsbro gossip events wait 'shinken-restart' --timeout 20
if [ $? != 0 ]; then
   echo "ERROR: the nagios module did not restart nagios"
   cat /var/log/opsbro/module.shinken.log
   cat /var/log/opsbro/daemon.log
   exit 2
fi

nagios -v /etc/nagios/nagios.cfg

ls -R /etc/nagios/

# Start opsbro and assert that the cfg file of the local element is created
NB_CFG=$(ls -1 /etc/nagios/objects/agent/*cfg | wc -l)

if [ $NB_CFG == 0 ]; then
   echo "ERROR: the cfg file for nagios was not created!"
   exit 2
fi

# Nagios check should be OK
NAGIOS_CHECK=$(nagios -v /etc/nagios/nagios.cfg)

if [ $? != 0 ]; then
   echo "ERROR: the nagios check is not happy"
   printf "%s" "$NAGIOS_CHECK"
   exit 2
fi

ls -thor /var/log/opsbro/

cat /var/log/opsbro/module.shinken.log

opsbro agent info

# Let a loop for opsbro to send checks to Nagios
sleep 15

# There sould be some alerts now in nagios log
EXPORTED_CHECKS=$(cat /var/nagios/nagios.log | grep 'PROCESS_SERVICE_CHECK_RESULT' | wc -l)

if [ $EXPORTED_CHECKS == 0 ]; then
   echo "ERROR: the checks executions are not send into nagios"
   cat /var/nagios/nagios.log
   exit 2
fi

exit_if_no_crash "OK:  nagios cfg export is working as expected (node is exported into CFG and checks are launched and received by Nagios)"
