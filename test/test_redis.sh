#!/usr/bin/env bash

# Start redis
redis-server&

sleep 20

test/assert_group.sh "redis"
if [ $? != 0 ]; then
    echo "ERROR: redis group is not set"
fi


RES=$(opsbro evaluator eval "{{collector.redis.available}} == True" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: redis collectors is fail {{collector.redis.available}} == True => $RES"
    opsbro collectors show redis
    exit 2
fi

RES=$(opsbro evaluator eval "{{collector.redis.connected_clients}} >= 1" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: redis collectors is fail {{collector.redis.connected_clients}} >= 1 => $RES"
    opsbro collectors show redis
    exit 2
fi


opsbro collectors show redis
echo "Redis is OK"


