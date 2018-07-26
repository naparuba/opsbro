#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

# We will try to add a group to the agent configuration, all in hot mode
/etc/init.d/opsbro start

opsbro agent parameters add groups test-group-1
if [ $? != 0 ]; then
    echo "ERROR: the agent parameters add groups did fail."
    exit 2
fi

opsbro agent parameters add groups test-group-2
if [ $? != 0 ]; then
    echo "ERROR: the agent parameters add groups did fail."
    exit 2
fi

opsbro agent info | grep 'Groups' | grep test-group-2
if [ $? != 0 ]; then
    echo "ERROR: the agent parameters add groups did fail."
    opsbro agent info
    exit 2
fi

# Now remove it
opsbro agent parameters remove groups test-group-1
if [ $? != 0 ]; then
    echo "ERROR: the agent parameters add groups did fail."
    exit 2
fi


# groups 1 should NOT be there
print_header "Checking that group 1 is not more present"
opsbro agent info | grep 'Groups' | grep test-group-1
if [ $? == 0 ]; then
    echo "ERROR: the agent parameters add groups did fail."
    opsbro agent info
    exit 2
fi

print_header "OK:  CLI groups add is working well"
