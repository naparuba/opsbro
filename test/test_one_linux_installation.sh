#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

##############################################################################
print_header "Installation"

$PYTHON_EXE setup.py install
if [ $? != 0 ]; then
   echo "ERROR: installation failed!"
   exit 2
fi

##############################################################################
print_header "Starting"
# Try to start daemon, but we don't want systemd hook there
SYSTEMCTL_SKIP_REDIRECT=1 /etc/init.d/opsbro --debug start
if [ $? != 0 ]; then
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/*log
   ps axjf
   echo "ERROR: daemon start failed!"
   exit 2
fi

# NOTE: the init script already wait for agent end of initialization

##############################################################################
print_header "Info"

opsbro agent info
if [ $? != 0 ]; then
   echo "ERROR: information get failed!"
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/*log
   ps axjf
   exit 2
fi

print_header "Address"

# Is there an address used by the daemon?
echo "Checking agent addr"
ADDR=$(opsbro agent print local-addr)
if [ "X$ADDR" == "X" ]; then
   echo "The opsbro daemon do not have a valid address."
   echo $(opsbro agent info)
   exit 2
fi
echo "Address: $ADDR"

##############################################################################
print_header "linux Group"

echo "Checking linux group"
# Check if linux group is set
test/assert_group.sh "linux"
if [ $? != 0 ]; then
   echo "ERROR: the group linux is missing!"
   exit 2
fi

##############################################################################
print_header "Docker container group"
# Check if docker-container group is set
echo "Checking agent docker group"

test/assert_group.sh "docker-container"
if [ $? != 0 ]; then
   echo "ERROR: the group docker-container is missing!"
   exit 2
fi

##############################################################################
print_header "Linux PACK: iostats coutners"
IOSTATS=$(opsbro collectors show iostats)

printf "%s" "$IOSTATS" | grep read_bytes >/dev/null
if [ $? != 0 ]; then
   echo "ERROR: the iostats collector do not seems to be working"
   printf "$IOSTATS"
   exit 2
fi

echo "Pack: iostats counters are OK"

##############################################################################
print_header "Linux PACK: cpustats counters"
CPUSTATS=$(opsbro collectors show cpustats)

printf "%s" "$CPUSTATS" | grep 'cpu_all.%idle' >/dev/null
if [ $? != 0 ]; then
   echo "ERROR: the cpustats collector do not seems to be working"
   printf "$CPUSTATS"
   exit 2
fi

echo "Pack: cpustats counters are OK"

##############################################################################
print_header "Runtime package detection"

# We are trying the fping package unless the distro test did ask us another
if [ "X$TEST_PACKAGE_NAME" == "X" ]; then
   TEST_PACKAGE_NAME=fping
fi

echo " * Testing simple package"
assert_one_package_can_be_installed_and_detected "$TEST_PACKAGE_NAME"

# We are trying the fping package unless the distro test did ask us another
if [ "X$TEST_PACKAGE_NAME_VIRTUAL" == "X" ]; then
   echo " * No virtual package is defined for this distribution, skipping the virtal package test."
else
   echo " * Testing virtual package detection"
   assert_one_package_can_be_installed_and_detected "$TEST_PACKAGE_NAME_VIRTUAL"
fi

echo "PACKAGE: the runtime package detection is working well"

print_header "LINUX PACK:  networktraffic counters"
NETWORKSTATS=$(opsbro collectors show networktraffic)

printf "%s" "$NETWORKSTATS" | grep 'recv_bytes/s'
if [ $? != 0 ]; then
   echo "ERROR: the networkstats collector do not seems to be working"
   printf "$NETWORKSTATS \n"
   cat /var/log/opsbro/collector.networktraffic.log
   exit 2
fi
echo "Pack: networkstats counters are OK"

# Some old distro do not like open port test (like centos6)
if [ "X$SKIP_OPENPORTS" != "XTrue" ]; then
   print_header "STANDARD LINUX PACK:  openports"
   OPENPORTS=$(opsbro collectors show openports)

   # The 6768 is the default agent one, so should be open
   printf "%s" "$OPENPORTS" | grep '6768'
   if [ $? != 0 ]; then
      echo "ERROR: the OPENPORTS collector do not seems to be working"
      printf "$OPENPORTS"
      cat /var/log/opsbro/collectors*
      exit 2
   fi
   echo "Pack: openports counters are OK"
fi

print_header "KV Store (sqlite/leveldb)"

function test_key_store() {
   KEY="SUPERKEY/33"
   VALUE="SUPERVALUE"

   echo " - do not exists"
   GET=$(opsbro kv-store get $KEY)
   if [ $? == 0 ]; then
      echo "There should not be key $KEY"
      echo $GET
      exit 2
   fi

   echo " - set"
   SET=$(opsbro kv-store put $KEY $VALUE)
   if [ $? != 0 ]; then
      echo "There should be ok in set $KEY $VALUE"
      echo $SET
      exit 2
   fi

   echo " - get"
   GET=$(opsbro kv-store get $KEY)
   if [ $? != 0 ]; then
      echo "There should be key $KEY"
      echo $GET
      exit 2
   fi

   echo " - grep get"
   GET_GREP=$(echo $GET | grep $VALUE)
   if [ $? != 0 ]; then
      echo "There should be key $KEY $VALUE"
      opsbro --debug kv-store get $KEY
      cat /var/log/opsbro/key-value.log
      cat /var/log/opsbro/crash.log 2>/dev/null
      exit 2
   fi

   echo " - delete"
   DELETE=$(opsbro kv-store delete $KEY)
   if [ $? != 0 ]; then
      echo "There should be no more key $KEY"
      echo $DELETE
      exit 2
   fi

   echo " - get after delete"
   GET=$(opsbro kv-store get $KEY)
   if [ $? == 0 ]; then
      echo "There should not be key $KEY after delete"
      echo $GET
      exit 2
   fi
}

##############################################################################
# Some distro do not have access to sqlite, as it is unstable (centos 7.0 and 7.1)
if [ "X$TEST_SQLITE" == "XTrue" ]; then

   test_key_store

   echo "KV (sqlite): get/put/delete is working"

   ##############################################################################
   print_header "KV Store: leveldb"

   # First we must have the sqlite backend
   INFO=$(opsbro agent info)

   echo "$INFO" | grep sqlite
   if [ $? != 0 ]; then
      echo "ERROR: The kv backend should be sqlite"
      echo "$INFO"
      exit 2
   fi

fi # end of SQLITE

# Some distro do not have access to leveldb anymore...
if [ "X$SKIP_LEVELDB" == "X" ]; then

   # We need to install libs only if the sqlite was need
   if [ "X$TEST_SQLITE" == "XTrue" ]; then
      # Note: compilation of leveldb can be long (and depedency download too)
      opsbro compliance launch 'Install tuning libs' --timeout=300
      if [ $? != 0 ]; then
         echo "ERROR: Cannot install leveldb"
         opsbro compliance state
         opsbro compliance history
         #cat /var/log/opsbro/daemon.log
         exit 2
      fi
   fi

   /etc/init.d/opsbro restart

   sleep 1

   # Now must be leveldb
   INFO=$(opsbro agent info)

   echo "$INFO" | grep leveldb
   if [ $? != 0 ]; then
      echo "ERROR: The kv backend should be leveldb"
      echo "$INFO"
      exit 2
   fi

   echo "Leveldb install is OK"

   test_key_store

   echo "KV (leveldb): get/put/delete is working"
fi # end of LEVELDB

printf "\n\n"
printf "\n\n"

##########   Show internal threads
print_header "Internal threads comsumption"

OUTPUT=$(opsbro agent internal show-threads)
if [ $? != 0 ]; then
   echo "ERROR: agent internal show-threads did fail."
   echo "$OUTPUT"
   cat /var/log/opsbro/crash.log 2>/dev/null
   cat /var/log/opsbro/daemon.log
   exit 2
fi


##########   Show internal threads
print_header "Fast YAML lib"

OUTPUT=$(opsbro agent info | grep 'Fast Yaml')
if [ $? != 0 ]; then
   echo "ERROR: agent info did fail."
   echo "$OUTPUT"
   cat /var/log/opsbro/crash.log 2>/dev/null
   cat /var/log/opsbro/daemon.log
   exit 2
fi

echo "$OUTPUT" | grep 'MISSING'
if [ $? == 0 ]; then
   echo "ERROR: The python-yaml librairy is missing"
   echo "$OUTPUT"
   exit 2
fi

echo "Fast YAML is OK"


print_header "Test Gossip Encryption"
opsbro gossip zone key import --zone internet --key "NGNjZWI2ZmEyMzEyMTFlOA=="

# Try to start daemon, but we don't want systemd hook there
SYSTEMCTL_SKIP_REDIRECT=1 /etc/init.d/opsbro --debug restart
if [ $? != 0 ]; then
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/*log
   ps axjf
   echo "ERROR: daemon start failed due to encryption"
   exit 2
fi

# Check that the encrypted key is loaded
opsbro agent info | grep 'zone have a gossip key'
# shellcheck disable=SC2181
if [ $? != 0 ]; then
   echo "ERROR: Encrypted key seem to not be load"
   opsbro agent info
   exit 2
fi

print_header "Test monitoring checks"

STATE=$(opsbro monitoring state)
# cpu is
echo "$STATE" | grep 'cpu is'
if [ $? != 0 ]; then
   echo "ERROR: Cannot find CPU CHECK"
   echo "$STATE"
   exit 2
fi

# / is at
echo "$STATE" | grep '/ is at'
if [ $? != 0 ]; then
   echo "ERROR: Cannot find / CHECK"
   echo "$STATE"
   exit 2
fi

# load is at
echo "$STATE" | grep 'load is at'
if [ $? != 0 ]; then
   echo "ERROR: Cannot find Load average CHECK"
   echo "$STATE"
   exit 2
fi

# memory is
echo "$STATE" | grep 'memory is'
if [ $? != 0 ]; then
   echo "ERROR: Cannot find Memory CHECK"
   echo "$STATE"
   exit 2
fi

echo "All linux checks are running well"

##########
print_header "Test proctitle display"

ps aux | grep opsbro | grep 'running'
if [ $? != 0 ]; then
   echo "ERROR: Cannot find agent with process title changed (setproctitle)"
   ps aux | grep opsbro
   exit 2
fi
echo "Agent is with setproctitle name"


exit_if_no_crash "**** One linux installation is OK *****"
