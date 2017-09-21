#!/usr/bin/env bash

echo "Starting to test DNS module"

# Start it
/etc/init.d/opsbro start

sleep 2

# Enable DNS module
opsbro agent parameters add groups dns-listener

# Wait for detection and co
# TODO: why so long?
sleep 15


# Look which addr we dhould match
ADDR=$(opsbro agent info| grep 'Addr' | awk '{print $3}')

# linux is detected, so should return
echo "Looking for my own entry $ADDR"
OUT=$(dig -p 6766  @127.0.0.1 linux.group.local.opsbro)
printf "$OUT" | grep "$ADDR"
if [ $? != 0 ]; then
    echo "The DNS module do not seems to result"
    printf "$OUT"
    opsbro agent info
    exit 2
fi


echo "opsbro DNS module is OK"
