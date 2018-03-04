#!/usr/bin/env bash

echo "Starting to test Compliance"
chmod 777 /etc/passwd
chown news:news /etc/passwd

# Start daemon
/etc/init.d/opsbro start

# need 2 turns to detect & solve
sleep 2

OUT=$(ls -la /etc/passwd)


echo "$OUT" | grep -- "-rw-r--r--"
if [ $? != 0 ]; then
    echo "ERROR: rights are not valid, compliance enforcing is failing."
    echo "$OUT"
    opsbro compliance history
    opsbro compliance state
    exit 2
fi

echo "$OUT" | grep -- "root root"
if [ $? != 0 ]; then
    echo "ERROR: rights are not valid, compliance enforcing is failing."
    echo "$OUT"
    opsbro compliance history
    opsbro compliance state
    exit 2
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

check_history_entry "The file /etc/passwd owner (news) is not what expected: root"
check_history_entry "Fixing owner news into root"
check_history_entry "The file /etc/passwd group (news) is not what expected: root"
check_history_entry "Fixing group news into root"
check_history_entry "The file /etc/passwd permissions (777) are not what is expected:644"
check_history_entry "Fixing file /etc/passwd permissions 777 into 644"
check_history_entry "The file /etc/passwd owner (root) is OK"
check_history_entry "The file /etc/passwd group (root) is OK"
check_history_entry "The file /etc/passwd permissions (644) are OK"


echo "HISTORY"
echo "$HISTORY"

printf "\n ****** Result ***** \n"
echo "OK:  Compliance in enforcing mode is working: $OUT is 644/root/root"
