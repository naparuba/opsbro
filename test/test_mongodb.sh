#!/usr/bin/env bash

# Start mongodb
mongod -f /etc/mongod.conf

sleep 15

test/assert_tag.sh "mongodb"
if [ $? != 0 ]; then
    echo "ERROR: Mongodb tag is not set"
    exit 2
fi


RES=$(kunai evaluator eval "{{collector.mongodb.available}}==True" | tail -n 1)

if [ $RES != "True" ]; then
    echo "Fail: mongodb collectors is not running $RES"
    kunai collectors show mongodb
    exit 2
fi

kunai collectors show mongodb
echo "Mongodb is OK"


