#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh



# Fix: centos do not have mysqld on the PATH
export PATH=/usr/libexec/:$PATH

# Start mysql
# NOTE: /tmp because we are launched for debian & centos, so cannot have the same directories
mysqld --basedir=/usr --datadir=/var/lib/mysql --plugin-dir=/usr/lib64/mysql/plugin --log-error=/tmp/mariadb.log --pid-file=/tmp/mariadb.pid --socket=/var/lib/mysql/mysql.sock --user=mysql&
sleep 10
# Set root account available (set socket because debian try network)
/usr/bin/mysqladmin --socket=/var/lib/mysql/mysql.sock  -u root password 'secret'


# We will modify a pack, so overload it first
opsbro  packs overload global.mysql
opsbro  packs parameters set local.mysql.password        secret

if [ $? != 0 ]; then
    echo "ERROR: cannot set parameter"
    exit 2
fi

/etc/init.d/opsbro start


test/assert_group.sh "mysql"
if [ $? != 0 ]; then
    echo "ERROR: mysql group is not set"
    exit 2
fi

# Wait until the collector is ready
opsbro collectors wait-ok mysql
if [ $? != 0 ]; then
    echo "ERROR: Mysql collector is not responding"
    exit 2
fi

RES=$(opsbro evaluator eval "{{collector.mysql.max_used_connections}} == 1" | tail -n 1)
if [ $RES != "True" ]; then
    echo "Fail: mysql collectors is fail {{collector.mysql.max_used_connections}} == 1 => $RES"
    opsbro collectors show mysql
    exit 2
fi


opsbro collectors show mysql

print_header "Mysql is OK"


