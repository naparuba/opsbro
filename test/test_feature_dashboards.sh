#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test to play with dashboards"


opsbro dashboards show linux --interval 1 --occurences 10

if [ $? != 0 ]; then
      echo "ERROR: dashboard seems to have problems"
      exit 2
fi

exit_if_no_crash "opsbro playing dashboards is OK"
