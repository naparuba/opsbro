#!/usr/bin/env bash


sleep 30

echo "Starting to test Nagios test (dummy check)"
/usr/local/nagios/bin/nagios -v /usr/local/nagios/etc/nagios.cfg


opsbro state | grep 'This is the exit text' | grep 'WARNING'

if [ $? != 0 ]; then
    echo "ERROR: the nagios checks is not available."
    opsbro state
    exit 2
fi
echo "OK:  nagios checks are working"
