#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test Compliance for nginx install"

# Start daemon
/etc/init.d/opsbro start

# need 2 turns to detect & solve
sleep 2

OUT=$(opsbro compliance state)

echo "$OUT" | grep "TEST NGINX" | grep "NOT-ELIGIBLE" >/dev/null
if [ $? != 0 ]; then
   echo "Nginx compliance is not in NOT-ELIGIBLE"
   echo "$OUT"
   exit 2
fi

echo "$OUT"

# Ask for installation
touch /tmp/install_nginx

# WAIT 120s for the installation to be done (can be long due to packages downloads)
opsbro compliance wait-compliant "TEST NGINX" --timeout=120
if [ $? != 0 ]; then
   echo "Nginx compliance cannot be fixed in COMPLIANCE state in 60s"
   opsbro compliance state
   exit 2
fi

curl -s http://localhost | grep 'nginx'
if [ $? != 0 ]; then
   echo "ERROR: nginx is not working"
   opsbro compliance history
   ps axjf
   exit 2
fi

opsbro compliance state

exit_if_no_crash "nginx install compliance rule is OK"
