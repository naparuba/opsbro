#!/usr/bin/env bash

echo "Starting to test Compliance"
chmod 777 /etc/passwd
chown news:news /etc/passwd

# Start daemon
/etc/init.d/opsbro start

# wait a bit that the compliance rule is executed
sleep 10

OUT=$(ls -la /etc/passwd)


grep -- "-rw-r--r--" "$OUT"
if [ $? != 0 ]; then
    echo "ERROR: rights are not valid, compliance enforcing is failing."
    echo "$out"
    exit 2
fi

grep -- "root root" "$OUT"
if [ $? != 0 ]; then
    echo "ERROR: rights are not valid, compliance enforcing is failing."
    echo "$out"
    exit 2
fi


echo "OK:  Compliance in enforcing mode is working: $out is 644/root/root"
