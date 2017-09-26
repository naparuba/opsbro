#!/usr/bin/env bash


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Starting       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Try to start daemon, but we don't want systemd hook there
python bin/opsbro agent start --daemon

if [ $? != 0 ]; then
   echo "ERROR: daemon start failed!"
   exit 2
fi


#sleep 60


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Info           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

LIMIT=60
for ii in `seq 1 $LIMIT`; do
    echo "Checking agent info, loop $ii"
    python bin/opsbro agent info
    if [ $? != 0 ]; then
       if [ $ii == $LIMIT ]; then
           echo "ERROR: information get failed!"
           cat log/opsbro/daemon.log
           exit 2
       fi
       echo "Let more time to the agent to start, restart this test"
       continue
    fi
    # Test OK, we can break
    echo "DBG: FINISH loop $ii"
    break
done


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Address?       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

# Is there an address used by the daemon?
LIMIT=60
for ii in `seq 1 $LIMIT`; do
    echo "Checking agent addr, loop $ii"
    ADDR=$(python bin/opsbro agent info | grep Addr | awk '{print $2}')
    if [ "$ADDR" == "None" ]; then
       if [ $ii == $LIMIT ]; then
           echo "The opsbro daemon do not have a valid address."
           echo `python bin/opsbro agent info`
           exit 2
       fi
       echo "Let more time to the agent to start, restart this test"
       continue
    fi
    # Test OK, we can break
    echo "DBG: FINISH loop $ii"
    break
done

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Linux GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if linux group is set
LIMIT=60
for ii in `seq 1 $LIMIT`; do
    echo "Checking agent addr, loop $ii"
    RES=$(python bin/opsbro evaluator eval "have_group('linux')" | tail -n 1)

    if [ $RES != "True" ]; then
       if [ $ii == $LIMIT ]; then
           echo "ERROR: the group linux is missing!"
           exit 2
       fi
       echo "Let more time to the agent to start, restart this test"
       continue
    fi
    # Test OK, we can break
    echo "DBG: FINISH loop $ii"
    break
done

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Docker-container GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if docker-container group is set

LIMIT=60
for ii in `seq 1 $LIMIT`; do
    echo "Checking agent docker group, loop $ii"
    RES=$(python bin/opsbro evaluator eval "have_group('docker-container')" | tail -n 1)

    if [ $RES != "True" ]; then
       if [ $ii == $LIMIT ]; then
           echo "ERROR: the group docker-container is missing!"
           exit 2
       fi
       echo "Let more time to the agent to start, restart this test"
       continue
    fi
    # Test OK, we can break
    echo "DBG: FINISH loop $ii"
    break
done