#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

cd test

echo "   *********   Python unitary tests  ***********"

$PYTHON_EXE test_unixclient.py #TestUnixClient.test_unixclient_POST_ret_ascii_arg_ascii

exit 0

for ii in $(ls -1 test_*py); do
   printf " - %-50s" "$ii"
   OUTPUT=$($PYTHON_EXE $ii 2>&1)
   if [ $? != 0 ]; then
      echo ""
      echo "TEST: $ii FAIL:"
      echo "$OUTPUT"
      exit 2
   fi
   printf "OK\n"
done

echo "   ******  All tests are OK   ******"
exit 0
