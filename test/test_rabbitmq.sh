#!/usr/bin/env bash

# Start rabbit mq
rabbitmq-plugins enable rabbitmq_management
rabbitmq-server &

sleep 20

#test/assert_tag.sh "mysql"
#if [ $? != 0 ]; then
#    echo "ERROR: mysql tag is not set"
#fi


#RES=$(kunai evaluator eval "{{collector.mysql.max_used_connections}} >= 1" | tail -n 1)
#if [ $RES != "True" ]; then
#    echo "Fail: mysql collectors is fail {{collector.mysql.max_used_connections}} >= 1 => $RES"
#    kunai collectors show mysql
#    exit 2
#fi


kunai collectors show rabbitmq
echo "Rabbitmq is OK"


