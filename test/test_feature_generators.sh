#!/usr/bin/env bash

/etc/init.d/opsbro start



opsbro generators wait-compliant sshkeys
if [ $? != 0 ];then
   echo "ERROR: cannot have the sshkey generator as compliant"
   opsbro generators state
   opsbro generators history
   cat /var/log/opsbro/generator.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   exit 2
fi


echo "Starting to test Generator"

echo "**********************************************"
cat /tmp/authorized_keys.txt
echo "**********************************************"

grep "FIRST LINE" /tmp/authorized_keys.txt
if [ $? != 0 ]; then
    echo "ERROR: FIRST LINE is not in the generated file."
    exit 2
fi

grep "SSH Key deploy start" /tmp/authorized_keys.txt
if [ $? != 0 ]; then
    echo "ERROR: SSH Key deploy start is not in the generated file."
    exit 2
fi

grep "HERE" /tmp/authorized_keys.txt
if [ $? != 0 ]; then
    echo "ERROR: HERE is not in the generated file."
    exit 2
fi


grep "ENDING LINE" /tmp/authorized_keys.txt
if [ $? != 0 ]; then
    echo "ERROR: ENDING LINE is not in the generated file."
    exit 2
fi

HISTORY=$(opsbro generators history)

echo "$HISTORY" | grep 'Generator sshkeys did generate a new file at'
if [ $? != 0 ];then
   echo "ERROR: history should have the Generator sshkeys did generate a new file at entry"
   echo "$HISTORY"
   exit 2
fi


echo "$HISTORY" | grep -- '-0004: BLABLA'
if [ $? != 0 ];then
   echo "ERROR: history should have the -0004: BLABLA   entry"
   echo "$HISTORY"
   exit 2
fi

echo "$HISTORY"

echo "OK:  Generators are working"
