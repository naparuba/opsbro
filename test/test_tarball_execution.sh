#!/usr/bin/env bash


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Starting       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Try to start daemon, but we don't want systemd hook there
python bin/opsbro agent start --daemon

if [ $? != 0 ]; then
   echo "ERROR: daemon start failed!"
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Wait for initialization           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

opsbro agent wait-initialized --timeout 60
if [ $? != 0 ]; then
   echo "ERROR: daemon start failed!"
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Info           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"


echo "Checking agent info"
python bin/opsbro agent info
if [ $? != 0 ]; then
   echo "ERROR: information get failed!"
   cat log/opsbro/daemon.log
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Address?       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

# Is there an address used by the daemon?
echo "Checking agent addr"
ADDR=$(python bin/opsbro agent info | grep Addr | awk '{print $2}')
if [ "$ADDR" == "None" ]; then
   echo "The opsbro daemon do not have a valid address."
   python bin/opsbro agent info
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Linux GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

echo "Checking linux group"
RES=$(python bin/opsbro evaluator eval "have_group('linux')" | tail -n 1)

if [ $RES != "True" ]; then
   echo "ERROR: the group linux is missing!"
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Docker-container GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if docker-container group is set

echo "Checking agent docker group"
RES=$(python bin/opsbro evaluator eval "have_group('docker-container')" | tail -n 1)

if [ $RES != "True" ]; then
   echo "ERROR: the group docker-container is missing!"
   exit 2
fi
