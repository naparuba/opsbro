#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


opsbro compliance launch 'Install tuning libs' --timeout=300


print_header "Setting values in the agent file (UTF8 mode)"
# Now with UTF8 parameters
PNAME="SUPERTEST"
SET=$(opsbro agent parameters set process_name "$PNAME")
if [ $? != 0 ];then
    echo "ERROR: the set parameter do not support UTF8"
    echo "$SET"
    exit 2
fi

/etc/init.d/opsbro start
if [ $? != 0 ];then
    echo "ERROR: process name setting did fail"
    echo "$SET"
    cat /var/log/opsbro/daemon.log
    exit 2
fi

sleep 1

ps axjf | pgrep $PNAME
if [ $? != 0 ];then
    echo "ERROR: process $PNAME was not founded"
    ps axjf
    cat /var/log/opsbro/daemon.log
    exit 2
fi

echo "OK: process $PNAME is founded"
ps axjf

exit_if_no_crash "TEST OK"