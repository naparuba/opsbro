#!/usr/bin/env bash

GROUP=$1

printf "\n****************** [ Checking GROUP is set:  $GROUP  ] ******************\n"

LIMIT=10

for ii in `seq 1 $LIMIT`; do
    RES=$(opsbro evaluator eval "have_group('$GROUP')" | tail -n 1)

    if [ $RES != "True" ]; then
        if [ $ii == $LIMIT ]; then
           echo "Fail: check if group is set: have_group('$GROUP') ==> $RES"
           opsbro agent info | grep Groups
           opsbro evaluator eval "have_group('$GROUP')"
           exit 2
        fi
        echo "Let more time to the agent to start, restart this test"
        continue
    fi
    echo "    - dbg: finish loop: $ii"
    echo "GROUP: $GROUP is OK"
    echo ""
    break
done

