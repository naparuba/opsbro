#!/usr/bin/env bash

echo "Starting to test STATSD module"

# Enable STATSD module
opsbro agent parameters add groups statsd-listener


# Start it
/etc/init.d/opsbro start

cat /var/log/opsbro/daemon.log

# Wait for the numpy installation rule to be done
opsbro compliance wait-compliant "Install numpy if statsd module enabled" --timeout=60

# Look if the socket is open
netstat -laputen | grep '^udp' | grep 8125
if [ $? != 0 ]; then
    echo "The STATSD module did not open socket"
    opsbro agent info
    exit 2
fi

opsbro agent info

echo "opsbro Statsd module is OK"
