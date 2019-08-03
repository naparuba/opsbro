#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh



print_header "Starting to test CLI packs commands"


opsbro packs list
if [ $? != 0 ]; then
   echo "ERROR: the packs list did fail."
   exit 2
fi

# There should be none overloaded packs
opsbro packs list --only-overloads | grep 'No packs matchs the request'
if [ $? != 0 ]; then
   echo "ERROR: There should not be any overload packs by default."
   exit 2
fi

exit_if_no_crash "OK:  cli packs is working well"
