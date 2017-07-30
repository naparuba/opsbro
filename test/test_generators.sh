#!/usr/bin/env bash


sleep 30

echo "Starting to test Generator"


cat /tmp/authorized_keys.txt

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
