#!/usr/bin/env bash

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Installation   ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
python setup.py install

if [ $? != 0 ]; then
   echo "ERROR: installation failed!"
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Starting       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Try to start daemon, but we don't want systemd hook there
SYSTEMCTL_SKIP_REDIRECT=1 /etc/init.d/opsbro start
if [ $? != 0 ]; then
   echo "ERROR: daemon start failed!"
   exit 2
fi

#TODO: find a way for this sleep to be useless
# Sleep until the opsbro
sleep 1

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Wait for initialization finish       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Will wait 60s max if the daemon is not finish to launch all the init things (collectors, generators, and co)
time opsbro agent wait-initialized --timeout 60

if [ $? != 0 ]; then
   echo "ERROR: the agent did not initialize in time"
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Info           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

LIMIT=60
for ii in `seq 1 $LIMIT`; do
    echo "Checking agent info, loop $ii"
    opsbro agent info
    if [ $? != 0 ]; then
       if [ $ii == $LIMIT ]; then
           echo "ERROR: information get failed!"
           cat /var/log/opsbro/daemon.log
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
    ADDR=$(opsbro agent info | grep Addr | awk '{print $2}')
    if [ "$ADDR" == "None" ]; then
       if [ $ii == $LIMIT ]; then
           echo "The opsbro daemon do not have a valid address."
           echo `opsbro agent info`
           exit 2
       fi
       echo "Let more time to the agent to start, restart this test"
       continue
    fi
    # Test OK, we can break
    echo "    dbg: finish loop $ii"
    break
done

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Linux GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if linux group is set
echo "Checking agent addr, loop $ii"

test/assert_group.sh "linux"
if [ $? != 0 ]; then
    echo "ERROR: the group linux is missing!"
    exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Docker-container GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if docker-container group is set
echo "Checking agent docker group, loop $ii"

test/assert_group.sh "docker-container"
if [ $? != 0 ]; then
   echo "ERROR: the group docker-container is missing!"
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  STANDARD LINUX PACK:  iostats counters      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
IOSTATS=$(opsbro collectors show iostats)

printf "%s" "$IOSTATS" | grep read_bytes > /dev/null
if [ $? != 0 ]; then
   echo "ERROR: the iostats collector do not seems to be working"
   printf "$IOSTATS"
   exit 2
fi

echo "Pack: iostats counters are OK"


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  STANDARD LINUX PACK:  cpustats counters      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
CPUSTATS=$(opsbro collectors show cpustats)

printf "%s" "$CPUSTATS" | grep 'cpu_all.%idle' > /dev/null
if [ $? != 0 ]; then
   echo "ERROR: the cpustats collector do not seems to be working"
   printf "$CPUSTATS"
   exit 2
fi

echo "Pack: cpustats counters are OK"


#TODO: fis the networktraffic so it pop out directly at first loop
#echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  STANDARD LINUX PACK:  networktraffic counters      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
#NETWORKSTATS=$(opsbro collectors show networktraffic)

#printf "%s" "$NETWORKSTATS" | grep 'recv_bytes/s' > /dev/null
#if [ $? != 0 ]; then
#   echo "ERROR: the networkstats collector do not seems to be working"
#   printf "$NETWORKSTATS"
#   exit 2
#fi

#echo "Pack: networkstats counters are OK"

#TODO: openports need netstats
#echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  STANDARD LINUX PACK:  openports counters      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
#OPENPORTS=$(opsbro collectors show openports)

# The 6768 is the default agent one, so should be open
#printf "%s" "$OPENPORTS" | grep '6768' > /dev/null
#if [ $? != 0 ]; then
#   echo "ERROR: the OPENPORTS collector do not seems to be working"
#   printf "$OPENPORTS"
#   exit 2
#fi

#echo "Pack: openports counters are OK"


echo "************************************ One linux installation is OK *********************************************"