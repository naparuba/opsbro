#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

# We will try to add a group to the agent configuration, all in hot mode
/etc/init.d/opsbro start


opsbro agent internal show-threads
if [ $? != 0 ]; then
    echo "ERROR: agent internal show-threads did fail when it should have."
    cat /var/log/opsbro/crash.log 2>/dev/null
    exit 2
fi

exit_if_no_crash "OK:  internal show-threads is working well"
