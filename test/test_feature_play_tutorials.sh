#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test to play the tutorials"

opsbro tutorials list

ALL_TUTORIALS=$(opsbro tutorials list | awk '{print $5}' | grep -vE '^$')

DID_PLAY="0"
for tutorial in $ALL_TUTORIALS; do
   DID_PLAY="1"
   print_header "Playing tutorial $tutorial "
   opsbro tutorials show $tutorial
   if [ $? != 0 ]; then
      echo "ERROR: the tutorial $tutorial did not play well."
      exit 2
   fi
done

if [ $DID_PLAY == "0" ]; then
   echo "ERROR: no tutorial was play, please review this test"
   exit 2
fi

exit_if_no_crash "opsbro playing tutorials is OK"
