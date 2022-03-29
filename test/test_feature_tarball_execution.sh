#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Starting       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Try to start daemon, but we don't want systemd hook there
$PYTHON_EXE bin/opsbro agent start --daemon

if [ $? != 0 ]; then
   echo "ERROR: daemon start failed!"
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Wait for initialization           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

$PYTHON_EXE bin/opsbro agent wait-initialized --timeout 60
if [ $? != 0 ]; then
   echo "ERROR: daemon start failed!"
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Info           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

echo "Checking agent info"
$PYTHON_EXE bin/opsbro agent info
if [ $? != 0 ]; then
   echo "ERROR: information get failed!"
   cat log/opsbro/daemon.log
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Address?       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

# Is there an address used by the daemon?
echo "Checking agent addr"
ADDR=$($PYTHON_EXE bin/opsbro agent info | grep Addr | awk '{print $2}')
if [ "$ADDR" == "None" ]; then
   echo "The opsbro daemon do not have a valid address."
   $PYTHON_EXE bin/opsbro agent info
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Linux GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

echo "Checking linux group"
RES=$($PYTHON_EXE bin/opsbro evaluator eval "is_in_group('linux')" | tail -n 1)

if [ $RES != "True" ]; then
   echo "ERROR: the group linux is missing!"
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Docker-container GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if docker-container group is set

echo "Checking agent docker group"
RES=$($PYTHON_EXE bin/opsbro evaluator eval "is_in_group('docker-container')" | tail -n 1)

if [ $RES != "True" ]; then
   echo "ERROR: the group docker-container is missing!"
   exit 2
fi

exit_if_no_crash "Tarball execution"
