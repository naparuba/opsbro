#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh



# Start redis
redis-server&

/etc/init.d/opsbro start


test/assert_group.sh "redis"
if [ $? != 0 ]; then
    echo "ERROR: redis group is not set"
fi


# Wait until the collector is ready
opsbro collectors wait-ok redis
if [ $? != 0 ]; then
    echo "ERROR: Redis collector is not responding"
    opsbro collectors show redis
    exit 2
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

exit_if_no_crash "Redis is OK"


