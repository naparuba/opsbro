#!/usr/bin/env bash

TAG=$1

printf "\n****************** [ Checking TAG is set:  $TAG  ] ******************\n"

RES=$(opsbro evaluator eval "have_tag('$TAG')" | tail -n 1)

if [ $RES != "True" ]; then
    echo "Fail: check if tag is set: have_tag('$TAG') ==> $RES"
    opsbro agent info | grep Tags
    exit 2
fi

echo "TAG: $TAG is OK"
echo ""

