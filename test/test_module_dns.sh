#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

function test_dns_query() {
   QUERY="$1"
   MATCH_IP="$2"

   # linux is detected, so should return
   echo "Looking for the $MATCH_IP with the query $QUERY"
   OUT=$(dig -p 6766 @127.0.0.1 $QUERY)
   printf "$OUT" | grep "$MATCH_IP"
   if [ $? != 0 ]; then
      echo "The DNS module do not seems to result"
      printf "$OUT"
      opsbro agent info
      cat /var/log/opsbro/module.dns-listener.log
      opsbro agent modules state
      hostname
      ip addr show
      ping -c 1 $(hostname)
      exit 2
   fi

   # Also the local dsnmasq
   echo "Looking for the $MATCH_IP with the query $QUERY but with the system DNS"
   OUT=$(dig $QUERY)
   printf "$OUT" | grep "$MATCH_IP"
   if [ $? != 0 ]; then
      echo "The DNS module do not seems to result"
      printf "$OUT"
      opsbro agent info
      opsbro compliance history
      cat /var/log/opsbro/module.dns-listener.log
      opsbro agent modules state
      hostname
      ping -c 1 $(hostname)
      cat /etc/resolv.conf
      cat /etc/dnsmasq.d/opsbro.conf
      ps axjf
      netstat -laputen | grep LISTEN
      exit 2
   fi

}

print_header "Starting to test DNS module"

# Set a valid display name for debug
opsbro agent parameters set display_name "node-dns-listener"

# Start it
/etc/init.d/opsbro --debug start

# Enable DNS module
opsbro agent parameters add groups dns-listener

print_header "Wait for dns relay"
opsbro compliance wait-compliant "Install local dns relay" --timeout=60
if [ $? != 0 ]; then
   echo "ERROR: the local dns cannot be installed"
   opsbro generators state
   opsbro generators history
   cat /var/log/opsbro/generator.log
   cat /var/log/opsbro/crash.log 2>/dev/null
fi

print_header "Checking module is working"
# Now look we are ready
# Look which addr we dhould match
ADDR=$(opsbro agent print public-addr)

if [ "X$ADDR" == "X" ]; then
   echo "ERROR: cannot look Address"
   opsbro agent info
   exit 2
fi

print_header "Testing Name DNS queries"

echo "Looking for my own entry $ADDR directly on daemon with a name query"
test_dns_query "node-dns-listener.name.local.opsbro" "$ADDR"

print_header "Testing GROUP DNS queries"
echo "Looking for my own entry $ADDR directly on daemon with a group query"
test_dns_query "linux.group.local.opsbro" "$ADDR"

exit_if_no_crash "opsbro DNS module is OK"
