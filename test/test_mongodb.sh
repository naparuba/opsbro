#!/usr/bin/env bash

# Start mongodb
mongod -f /etc/mongod.conf

sleep 15

test/assert_group.sh "mongodb"
if [ $? != 0 ]; then
    echo "ERROR: Mongodb group is not set"
    exit 2
fi


RES=$(opsbro evaluator eval "{{collector.mongodb.available}}==True" | tail -n 1)

if [ $RES != "True" ]; then
    echo "Fail: mongodb collectors is not running $RES"
    opsbro collectors show mongodb
    exit 2
fi

opsbro collectors show mongodb
echo "Mongodb is OK"


