#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test agent parameters show"

opsbro agent parameters show

if [ $? != 0 ]; then
   echo "The opsbro agent parameters show show did fail"
   exit 2
fi

exit_if_no_crash "opsbro agent parameters show OK"
