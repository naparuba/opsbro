#!/usr/bin/env bash

# Start mysql
/usr/libexec/mysqld --basedir=/usr --datadir=/var/lib/mysql --plugin-dir=/usr/lib64/mysql/plugin --log-error=/var/log/mariadb/mariadb.log --pid-file=/var/run/mariadb/mariadb.pid --socket=/var/lib/mysql/mysql.sock --user=mysql&

sleep 10
# Set root account available
/usr/bin/mysqladmin -u root password 'root'

sleep 20

test/assert_tag.sh "mysql"
if [ $? != 0 ]; then
    echo "ERROR: mysql tag is not set"
    exit 2
fi


RES=$(opsbro evaluator eval "{{collector.mysql.max_used_connections}} >= 1" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: mysql collectors is fail {{collector.mysql.max_used_connections}} >= 1 => $RES"
    opsbro collectors show mysql
    exit 2
fi


opsbro collectors show mysql
echo "Mysql is OK"


