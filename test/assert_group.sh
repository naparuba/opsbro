#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

GROUP=$1

printf "\n****************** [ Checking GROUP is set:  $GROUP  ] ******************\n"

# Assert group only if agent is stable
opsbro detectors wait-group $GROUP --timeout=60

if [ $? != 0 ]; then
   echo "ERROR: cannot check group is agent is not started or stable"
   opsbro agent info
   exit 2
fi

# Also check that the is_in_group call is still working
RES=$(opsbro evaluator eval "is_in_group('$GROUP')")
if [ $? != 0 ]; then
   echo "ERROR: cannot check group: $RES"
   exit 2
fi

RES=$(echo "$RES" | tail -n 1)

if [ $RES != "True" ]; then
   echo "Fail: check if group is set: is_in_group('$GROUP') ==> $RES"
   opsbro agent info | grep Groups
   opsbro evaluator eval "is_in_group('$GROUP')"
   exit 2
fi

echo "GROUP: $GROUP is OK"
