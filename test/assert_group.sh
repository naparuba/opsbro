#!/usr/bin/env bash

GROUP=$1

printf "\n****************** [ Checking GROUP is set:  $GROUP  ] ******************\n"

RES=$(opsbro evaluator eval "have_group('$GROUP')" | tail -n 1)

if [ $RES != "True" ]; then
    echo "Fail: check if group is set: have_group('$GROUP') ==> $RES"
    opsbro agent info | grep Groups
    exit 2
fi

echo "GROUP: $GROUP is OK"
echo ""

