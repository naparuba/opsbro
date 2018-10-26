#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


/etc/init.d/opsbro start

sleep 60

print_header "Starting to test Nagios test (dummy check)"


echo "Checking nagios check outputs"

opsbro monitoring state | grep 'This is the exit text' | grep WARNING
if [ $? != 0 ]; then
   echo "ERROR: the nagios checks is not available."
   opsbro monitoring state
   exit 2
fi


exit_if_no_crash "OK:  nagios checks are working"
