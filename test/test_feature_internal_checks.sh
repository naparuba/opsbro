#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


/etc/init.d/opsbro start

sleep 60

print_header "Starting to test Internal test (dummy check)"


opsbro monitoring state | grep 'CRITICAL OUTPUT'
if [ $? != 0 ]; then
    echo "ERROR: the internal checks is not available."
    opsbro monitoring state
    exit 2
fi


HISTORY=$(opsbro monitoring history)
echo "$HISTORY" |grep 'System Load Average'
if [ $? != 0 ];then
   echo "ERROR: the history seems to be missing System Load Average entry"
   echo "$HISTORY"
   exit 2
fi

echo "$HISTORY"

print_header "OK:  internal checks are working"
