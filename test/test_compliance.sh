#!/usr/bin/env bash

echo "Starting to test Compliance"
chmod 777 /etc/passwd
chown news:news /etc/passwd

# Start daemon
/etc/init.d/opsbro start


OUT=$(ls -la /etc/passwd)


echo "$OUT" | grep -- "-rw-r--r--"
if [ $? != 0 ]; then
    echo "ERROR: rights are not valid, compliance enforcing is failing."
    echo "$OUT"
    exit 2
fi

echo "$OUT" | grep -- "root root"
if [ $? != 0 ]; then
    echo "ERROR: rights are not valid, compliance enforcing is failing."
    echo "$OUT"
    exit 2
fi


echo "OK:  Compliance in enforcing mode is working: $OUT is 644/root/root"
