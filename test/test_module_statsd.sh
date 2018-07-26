#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


print_header "Starting to test STATSD module"

# Enable STATSD module
opsbro agent parameters add groups statsd-listener


# Start it
/etc/init.d/opsbro start

cat /var/log/opsbro/daemon.log

# Wait for the numpy installation rule to be done
opsbro compliance wait-compliant "Install numpy if statsd module enabled" --timeout=60

# Look if the socket is open
echo "Look if the 8125 port is OPEN"
netstat -laputen | grep '^udp' | grep 8125
if [ $? != 0 ]; then
    echo "The STATSD module did not open socket"
    opsbro agent info
    opsbro agent modules state
    exit 2
fi

print_header "opsbro Statsd module is OK"
