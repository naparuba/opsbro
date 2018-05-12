#!/usr/bin/env bash


/etc/init.d/opsbro start

sleep 60

echo "Starting to test Internal test (dummy check)"


opsbro monitoring state | grep 'CRITICAL OUTPUT'
if [ $? != 0 ]; then
    echo "ERROR: the internal checks is not available."
    opsbro monitoring state
    exit 2
fi


HISTORY=$(opsbro monitoring history)
echo "$HISTORY" |grep 'System Load Average'
if [ $? != 0 ];then
   echo "ERROR: the history seems to be missing System Load Average entry"
   echo "$HISTORY"
   exit 2
fi

echo "$HISTORY"

echo "OK:  internal checks are working"
