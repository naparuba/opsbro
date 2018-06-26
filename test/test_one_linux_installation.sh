#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


##############################################################################
print_header "Installation"

python setup.py install
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
    echo `opsbro agent info`
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

printf "%s" "$IOSTATS" | grep read_bytes > /dev/null
if [ $? != 0 ]; then
   echo "ERROR: the iostats collector do not seems to be working"
   printf "$IOSTATS"
   exit 2
fi

echo "Pack: iostats counters are OK"


##############################################################################
print_header "Linux PACK: cpustats counters"
CPUSTATS=$(opsbro collectors show cpustats)

printf "%s" "$CPUSTATS" | grep 'cpu_all.%idle' > /dev/null
if [ $? != 0 ]; then
   echo "ERROR: the cpustats collector do not seems to be working"
   printf "$CPUSTATS"
   exit 2
fi

echo "Pack: cpustats counters are OK"


##############################################################################
print_header "Runtime package detection"

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
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/*log
   ps axjf
   exit 2
fi


echo "PACKAGE: the runtime package detection is working well"


#TODO: fis the networktraffic so it pop out directly at first loop
# printf "\n\n"
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
#printf "\n\n"
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

print_header "KV Store (sqlite/leveldb)"


function test_key_store {
    KEY="SUPERKEY/33"
    VALUE="SUPERVALUE"

    echo " - do not exists"
    GET=$(opsbro kv-store get $KEY)
    if [ $? == 0 ];then
       echo "There should not be key $KEY"
       echo $GET
       exit 2
    fi

    echo " - set"
    SET=$(opsbro kv-store put $KEY $VALUE)
    if [ $? != 0 ];then
       echo "There should be ok in set $KEY $VALUE"
       echo $SET
       exit 2
    fi

    echo " - get"
    GET=$(opsbro kv-store get $KEY)
    if [ $? != 0 ];then
       echo "There should be key $KEY"
       echo $GET
       exit 2
    fi

    echo " - grep get"
    GET_GREP=$(echo $GET | grep $VALUE)
    if [ $? != 0 ];then
       echo "There should be key $KEY $VALUE"
       echo $GET_GREP
       exit 2
    fi

    echo " - delete"
    DELETE=$(opsbro kv-store delete $KEY)
    if [ $? != 0 ];then
       echo "There should be no more key $KEY"
       echo $DELETE
       exit 2
    fi

    echo " - get after delete"
    GET=$(opsbro kv-store get $KEY)
    if [ $? == 0 ];then
       echo "There should not be key $KEY after delete"
       echo $GET
       exit 2
    fi
}

##############################################################################
# Some distro do not have access to sqlite, as it is unstable (centos 7.0 and 7.1)
if [ "X$SKIP_SQLITE" == "X" ];then

    test_key_store

    echo "KV (sqlite): get/put/delete is working"


    ##############################################################################
    print_header "KV Store: leveldb"

    # First we must have the sqlite backend
    INFO=$(opsbro agent info)

    echo "$INFO" | grep sqlite
    if [ $? != 0 ];then
       echo "ERROR: The kv backend should be sqlite"
       echo "$INFO"
       exit 2
    fi

fi  # end of SQLITE


# Some distro do not have access to leveldb anymore...
if [ "X$SKIP_LEVELDB" == "X" ];then

    # Note: compilation of leveldb can be long
    opsbro compliance launch 'Install Leveldb' --timeout=180
    if [ $? != 0 ];then
       echo "ERROR: Cannot install leveldb"
       opsbro compliance state
       opsbro compliance history
       cat /var/log/opsbro/daemon.log
       exit 2
    fi

    /etc/init.d/opsbro restart

    sleep 1

    # Now must be leveldb
    INFO=$(opsbro agent info)

    echo "$INFO" | grep leveldb
    if [ $? != 0 ];then
       echo "ERROR: The kv backend should be leveldb"
       echo "$INFO"
       exit 2
    fi

    echo "Leveldb install is OK"

    test_key_store

    echo "KV (leveldb): get/put/delete is working"
fi  # end of LEVELDB

printf "\n\n"
printf "\n\n"
echo "************************************ One linux installation is OK *********************************************"
