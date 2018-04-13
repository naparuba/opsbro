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

# NOTE: the init script already wait for agent end of initialization


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Info           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"


opsbro agent info
if [ $? != 0 ]; then
    echo "ERROR: information get failed!"
    cat /var/log/opsbro/daemon.log
    exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Address?       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

# Is there an address used by the daemon?
echo "Checking agent addr"
ADDR=$(opsbro agent info | grep Addr | awk '{print $2}')
if [ "$ADDR" == "None" ]; then
    echo "The opsbro daemon do not have a valid address."
    echo `opsbro agent info`
    exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Linux GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

echo "Checking linux group"
# Check if linux group is set
test/assert_group.sh "linux"
if [ $? != 0 ]; then
    echo "ERROR: the group linux is missing!"
    exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Docker-container GROUP      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if docker-container group is set
echo "Checking agent docker group"

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


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  Runtime package detection      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"

# We are trying the fping package unless the distro test did ask us another
if [ "X$TEST_PACKAGE_NAME" == "X" ];then
   TEST_PACKAGE_NAME=fping
fi
echo "We should not have the $TEST_PACKAGE_NAME package installed"
opsbro evaluator wait-eval-true "has_package('$TEST_PACKAGE_NAME')" --timeout=2
if [ $? == 0 ];then
   echo "ERROR: should not be the $TEST_PACKAGE_NAME package installed"
   exit 2
fi

MASSIVE_INSTALL_LOG=/tmp/massive_install_test
> $MASSIVE_INSTALL_LOG
/dnf_install     $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG
/yum_install     $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG
/apt_get_install $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG
/apk_add         $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG
/zypper_install  $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG


# We let debian take some few seconds before detect it (5s cache for more perfs on docker only)
opsbro evaluator wait-eval-true "has_package('$TEST_PACKAGE_NAME')" --timeout=10
if [ $? != 0 ];then
   echo "ERROR: the $TEST_PACKAGE_NAME package should have been detected"
   cat $MASSIVE_INSTALL_LOG
   exit 2
fi


echo "PACKAGE: the runtime package detection is working well"


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