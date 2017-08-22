#!/usr/bin/env bash

/etc/init.d/opsbro start

sleep 30

echo "Starting to test APIS"


echo "********** /packs *********"
RES=$(curl -s http://localhost:6768/packs | jq '.global.hypervisor[0].name')

if [ $? != 0 ] || [ $RES == "null" ]; then
    echo "ERROR: the /packs do not returns good results: $RES"
    exit 2
fi
echo "OK:  /packs did return $RES"

echo "All APIS are OK"