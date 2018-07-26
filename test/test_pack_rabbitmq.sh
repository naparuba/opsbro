#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh



# Start rabbit mq
rabbitmq-plugins enable rabbitmq_management --offline
if [ $? != 0 ];then  # centos do not manage --offline
   rabbitmq-plugins enable rabbitmq_management
fi
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
    opsbro collectors state
    exit 2
fi

RES=$(opsbro evaluator eval "{{collector.rabbitmq.queue_totals.messages}} >= 0" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: mysql collectors is fail {{collector.rabbitmq.queue_totals.messages}} >= 0 => $RES"
    opsbro collectors show rabbitmq
    exit 2
fi


opsbro collectors show rabbitmq

print_header "Rabbitmq is OK"


