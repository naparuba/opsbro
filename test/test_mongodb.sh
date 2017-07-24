#!/usr/bin/env bash

# Start mongodb
mongod -f /etc/mongod.conf

sleep 15

RES=$(kunai evaluator eval "{{collector.mongodb.available}}==True" | tail -n 1)

if [ $RES != "True" ]; then
    echo "Fail: mongodb collectors is not running $RES"
    kunai collectors show mongodb
    exit 2
fi

kunai collectors show mongodb
echo "Mongodb is OK"


