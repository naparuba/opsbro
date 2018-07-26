#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


# Start daemon
/etc/init.d/opsbro start


print_header "Starting to test Compliance"
touch /tmp/install_cock



# WAIT 60s for the installation to be done (can be long due to packages downloads)
opsbro compliance wait-compliant "TEST COCK" --timeout=120
if [ $? != 0 ]; then
    echo "Cockroachdb compliance cannot be fixed in COMPLIANCE state in 120s"
    opsbro compliance state
    exit 2
fi

opsbro compliance state
opsbro compliance history

# Let the database the time to starts
sleep 5

ps aux | grep cockroach | grep -v grep
if [ $? != 0 ];then
   echo "ERROR: The database is not ready"
   ps axjf
fi


export HISTORY=$(opsbro compliance history)

check_history_entry() {
   ENTRY="$1"
   echo "$HISTORY" | grep -- "$ENTRY"
   if [ $? != 0 ]; then
      echo "Missing history entry: $ENTRY"
      echo "$HISTORY"
      exit 2
   fi
   echo "OK the entry $ENTRY is present in the history"
}

check_history_entry "The file at https://binaries.cockroachdb.com/cockroach-v2.0.0.linux-amd64.tgz was download at /tmp/cockroach-v2.0.0.linux-amd64.tgz"
check_history_entry "The file at https://binaries.cockroachdb.com/cockroach-v2.0.0.linux-amd64.tgz is already present at /tmp/cockroach-v2.0.0.linux-amd64.tgz"


echo "HISTORY"
echo "$HISTORY"

printf "\n ****** Result ***** \n"
print_header "OK:  Compliance in enforcing mode is working"

exit 0