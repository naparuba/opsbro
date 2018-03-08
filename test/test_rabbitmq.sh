#!/usr/bin/env bash



# Start rabbit mq
rabbitmq-plugins enable rabbitmq_management
rabbitmq-server &

/etc/init.d/opsbro start

test/assert_group.sh "rabbitmq"
if [ $? != 0 ]; then
    echo "ERROR: rabbitmq group is not set"
fi

# Wait until the collector is ready
opsbro collectors wait-ok rabbitmq
if [ $? != 0 ]; then
    echo "ERROR: Rabbitmq collector is not responding"
    exit 2
fi

RES=$(opsbro evaluator eval "{{collector.rabbitmq.queue_totals.messages}} >= 0" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: mysql collectors is fail {{collector.rabbitmq.queue_totals.messages}} >= 0 => $RES"
    opsbro collectors show rabbitmq
    exit 2
fi


opsbro collectors show rabbitmq
echo "Rabbitmq is OK"


