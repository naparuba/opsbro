#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh >/dev/null

# Try to reduce startup load
set_to_minimal_gossip_core

# For this test, we prefer to have lower rotation value, just enought to have some files
export FORCE_LOG_ROTATION_PERIOD=2

# Debian 9 fakelie path
FAKELIB=/usr/lib/x86_64-linux-gnu/faketime/libfaketimeMT.so.1

cd /var/log/opsbro

function launch_as_end_of_day_day() {
   DAY="$1"
   echo " - Launching as day $DAY"
   /etc/init.d/opsbro stop >/dev/null

   # Fake the time in the lib
   # note: the @ is for "starts at"
   printf "@2019-02-$DAY 23:59:45" >/etc/faketimerc

   # FORCE_LOG_ROTATION_PERIOD: reduce the rotation time
   # FAKETIME_NO_CACHE: ask the lib to reload the faketimerc file every time
   # NO_FAKE_STAT: ask the lib to NOT fake file date, as the daemon is already doing it on rotation
   NO_FAKE_STAT=1 FORCE_LOG_ROTATION_PERIOD=3 FAKETIME_NO_CACHE=1 LD_PRELOAD=$FAKELIB /etc/init.d/opsbro --debug start >/dev/null
}

function check_rotation_day_present() {
   DAY="$1"
   echo "  * Looking for file : daemon.log.2019-02-$DAY"
   for ii in $(seq 1 60); do
      # First: look for a crash
      if [ -f /var/log/opsbro/crash.log ]; then
         echo "The daemon did crash"
         cat /var/log/opsbro/crash.log
         exit 2
      fi

      # Then look if retention is done
      if [ -f daemon.log.2019-02-$DAY ]; then
         echo "  * rotation file for DAY $DAY founded after $ii seconds"
         return 0
      fi
      sleep 1

   done
   # Not found after 60s: no retention done :(
   echo "ERROR: cannot find the rotation day $DAY"
   cat daemon.log
   ls -thor
   exit 2
}

function check_rotation_day_missing() {
   DAY="$1"
   echo "  * Looking for file MISSING : daemon.log.2019-02-$DAY"
   if [ -f daemon.log.2019-02-$DAY ]; then
      echo "ERROR: the rotation seems to be broken, the file is still there"
      ls -thor
      exit 2
   fi
   echo "   - the file is deleted"
   return 0
}

launch_as_end_of_day_day 11
check_rotation_day_present 11

launch_as_end_of_day_day 12
check_rotation_day_present 12

launch_as_end_of_day_day 13
check_rotation_day_present 13

launch_as_end_of_day_day 14
check_rotation_day_present 14

launch_as_end_of_day_day 15
check_rotation_day_present 15
# Starts to have deleted files
check_rotation_day_missing 11

launch_as_end_of_day_day 16
check_rotation_day_present 16
check_rotation_day_missing 12

exit_if_no_crash "Log rotation is OK"
