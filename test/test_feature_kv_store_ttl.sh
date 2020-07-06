#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh > /dev/null

# cannot set to minimal gossip as we WANT metrics :)


# Debian 9 fakelie path
FAKELIB=/usr/lib/x86_64-linux-gnu/faketime/libfaketimeMT.so.1

cd /var/log/opsbro

function launch_as_start_of_day_day {
   DAY="$1"
   echo " - Launching as day $DAY"
   /etc/init.d/opsbro stop > /dev/null

   # Fake the time in the lib
   # note: the @ is for "starts at"
   printf "@2019-02-$DAY 01:00:45" > /etc/faketimerc

   # FORCE_LOG_ROTATION_PERIOD: reduce the rotation time
   # FAKETIME_NO_CACHE: ask the lib to reload the faketimerc file every time
   # NO_FAKE_STAT: ask the lib to NOT fake file date, as the daemon is already doing it on rotation
   NO_FAKE_STAT=1 FAKETIME_NO_CACHE=1 LD_PRELOAD=$FAKELIB  /etc/init.d/opsbro --debug start > /dev/null
}


launch_as_start_of_day_day 01


# Must exists /var/lib/opsbro/kv_ttl/1549069200.ttl


sleep 30
echo "Looking at /var/lib/opsbro/kv_ttl/"
ls -thor /var/lib/opsbro/kv_ttl/
sleep 30
ls -thor /var/lib/opsbro/kv_ttl/

TTL_FILE=/var/lib/opsbro/kv_ttl/1549069200.ttl
if [ ! -f $TTL_FILE ];then
    echo "ERROR: the TTL file $TTL_FILE should be exists"
    cat /var/log/opsbro/key-value.log
    cat /var/log/opsbro/daemon.log
    exit 2
fi

echo "TTL FILE $TTL_FILE  is present"

/etc/init.d/opsbro restart

sleep 30
echo "Looking at /var/lib/opsbro/ttl/"
ls -thor /var/lib/opsbro/kv_ttl/
sleep 30
ls -thor /var/lib/opsbro/kv_ttl/

if [ -f $TTL_FILE ];then
    echo "ERROR: the TTL file $TTL_FILE should be missing"
    cat /var/log/opsbro/key-value.log
    cat /var/log/opsbro/daemon.log
    exit 2
fi

exit_if_no_crash "TTL is OK"
