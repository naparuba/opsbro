#!/usr/bin/env bash


sleep 30

echo "Starting to test Nagios test (dummy check)"



opsbro monitoring state | grep 'This is the exit text' | grep WARNING

if [ $? != 0 ]; then
    echo "ERROR: the nagios checks is not available."
    opsbro state
    exit 2
fi
echo "OK:  nagios checks are working"
