#!/usr/bin/env bash


opsbro generators wait-compliant sshkeys
if [ $? != 0 ];then
   echo "ERROR: cannot have the sshkey generator as compliant"
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

echo "OK:  Generators are working"
