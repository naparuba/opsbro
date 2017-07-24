#!/usr/bin/env bash

# Start redis
redis-server&

sleep 20

RES=$(kunai evaluator eval "{{collector.redis.available}} == True" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: redis collectors is fail {{collector.redis.available}} == True => $RES"
    kunai collectors show redis
    exit 2
fi

RES=$(kunai evaluator eval "{{collector.redis.connected_clients}} >= 1" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: redis collectors is fail {{collector.redis.connected_clients}} >= 1 => $RES"
    kunai collectors show redis
    exit 2
fi


kunai collectors show redis
echo "Redis is OK"


