#!/usr/bin/env bash

GROUP=$1

printf "\n****************** [ Checking GROUP is set:  $GROUP  ] ******************\n"

# Assert group only if agent is stable
opsbro agent wait-initialized --timeout 60

if [ $? != 0 ]; then
   echo "ERROR: cannot check group is agent is not started or stable"
   exit 2
fi

RES=$(opsbro evaluator eval "is_in_group('$GROUP')" | tail -n 1)
if [ $RES != "True" ]; then
   echo "Fail: check if group is set: is_in_group('$GROUP') ==> $RES"
   opsbro agent info | grep Groups
   opsbro evaluator eval "is_in_group('$GROUP')"
   exit 2
fi

echo "GROUP: $GROUP is OK"

