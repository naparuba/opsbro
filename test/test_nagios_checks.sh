#!/usr/bin/env bash


echo "Starting to test Nagios test (dummy check)"


echo "Checking nagios check outputs"

opsbro monitoring state | grep 'This is the exit text' | grep WARNING
if [ $? != 0 ]; then
   echo "ERROR: the nagios checks is not available."
   opsbro monitoring state
exit 2


echo "OK:  nagios checks are working"
