echo "Loading the common shell functions"

# If there is no python_exe set in the test, set the dfault system one
if [ "X$PYTHON_EXE" == "X" ];then
    export  PYTHON_EXE=python
fi

function print_header {
   printf "\n\n\n"
   printf '\033[94m¯`·.¸.·´¯`·.¸.·´¯`·.¸.·´\033[0m  \033[93m%-40s  \033[94m¯`·.¸.·´¯`·.¸.·´¯`·.¸.·´\033[0m\n\n' "$1"
}


function show_my_system_ip {
    ip addr show | grep 'scope global' | awk '{print $2}'
}


# Count the number of members in a STATE and check if they are NB==$2
function assert_state_count {
   STATS="$3"
   i=0
   until [ $i -ge 20 ]
   do
      STATS=$(opsbro gossip members)
      if [ $? != 0 ];then
         echo "ERROR: the daemon cannot answer to gossip member listing"
         cat /var/log/opsbro/gossip.log
         cat /var/log/opsbro/daemon.log
         cat /var/log/opsbro/crash.log 2>/dev/null
         exit 2
      fi
      NB=$(echo "$STATS" | grep "$1" | wc -l)
      if [ "$NB" == "$2" ]; then
          echo "OK: founded $NB $1 states nodes"
          return 0
      fi
      echo "OUPS: there should be $2 $1 but there are $NB after $i/20 try"
      i=$[$i+1]
      sleep 1
   done

   # Out and still not OK? we did fail
   echo "ERROR: `date` there should be $2 $1 but there are $NB after 20 try"
   echo "$STATS"
   cat /var/log/opsbro/gossip.log
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   opsbro gossip history
   exit 2
}


function wait_member_display_name_with_timeout {
    opsbro gossip wait-members --display-name "$1" --timeout $2
    if [ $? != 0 ]; then
       echo "ERROR: `date` the node with the display name $1 is not present after $2s"
       opsbro gossip members --detail
       cat /var/log/opsbro/daemon.log
       cat /var/log/opsbro/crash.log 2>/dev/null
       exit 2
    fi
}


function wait_event_with_timeout {
    opsbro gossip events wait $1 --timeout=$2
    if [ $? != 0 ]; then
         echo ""
         echo "FAIL `date` on event $1. Logs:"
         cat /var/log/opsbro/daemon.log
         cat /var/log/opsbro/gossip.log
         cat /var/log/opsbro/crash.log 2>/dev/null
         echo "ERROR: `date` I do not have the event $1 after $2 seconds"
         exit 2
    fi
}


function assert_can_ping {
    echo "Looking if we can ping $1"
    ping -c 1 "$1"
    if [ $? != 0 ];then
       echo "ERROR: cannot ping $1"
       exit 2
    fi
    echo "OK we can ping $1"
}


function assert_cannot_ping {
    echo "Looking if we cannot ping $1"
    ping -c 1 "$1"
    if [ $? == 0 ];then
       echo "ERROR: we still can ping $1"
       exit 2
    fi
    echo "OK we cannot ping $1"
}


function assert_in_file {
    LINE="$1"
    FILE="$2"
    printf "ASSERTING LINE:    %-30s in the file   %-30s :" "$LINE" "$FILE"
    grep "$LINE" "$FILE" >/dev/null
    if [ $? != 0 ];then
        printf "\n"
        echo "ERROR: cannot find the line $LINE in the agent file $FILE"
        cat $FILE
        exit 2
    fi
    printf " √\n"
}


function assert_directory_missing {
    DIRECTORY="$1"
    printf "ASSERTING non exist directory: %-30s:" "$DIRECTORY"
    if [ -d $DIRECTORY ];then
       printf "\n"
       echo "ERROR: The directory $DIRECTORY does exists, and it is not normal"
       exit 2
    fi
    printf " √\n"
}


function assert_directory_exists {
    DIRECTORY="$1"
    printf "ASSERTING exist directory: %-30s:" "$DIRECTORY"
    if [ ! -d $DIRECTORY ];then
       printf "\n"
       echo "ERROR: The directory $DIRECTORY does not exists, and it is not normal"
       exit 2
    fi
    printf " √\n"
}


function assert_no_crash {
   if [ -f /var/log/opsbro/crash.log ];then
       echo "ERROR: BIG CRASH"
       cat /var/log/opsbro/crash.log
       exit 2
    fi
}


# In this function, we are exiting the TEST, but first look
# if the crash.log file is not present. If so, maybe the daemon did crash in a way,
# and if so, display it and exit BAD because this is not tolerated
function exit_if_no_crash {
    print_header "Ending"

    assert_no_crash
    printf " - $1\n"
    printf " - Clean exit: OK √\n"
    exit 0
}


# We configure the daemon so only the gossip part is enabled
# to lower the server load during test
function set_to_minimal_gossip_core {
    for param in automatic_detection_topic_enabled monitoring_topic_enabled metrology_topic_enabled configuration_automation_topic_enabled system_compliance_topic_enabled; do
        opsbro agent parameters set $param false
        if [ $? != 0 ];then
           echo "ERROR: cannot set the agent parameter: $param"
           exit 2
        fi
    done
}


# We configure the daemon so only the gossip & detection are working
function set_to_only_gossip_and_detection {
    for param in monitoring_topic_enabled configuration_automation_topic_enabled system_compliance_topic_enabled; do
        opsbro agent parameters set $param false
        if [ $? != 0 ];then
           echo "ERROR: cannot set the agent parameter: $param"
           exit 2
        fi
    done
}

# We configure the daemon so only the gossip & config_automation
function set_to_only_gossip_and_config_automation {
    for param in monitoring_topic_enabled automatic_detection_topic_enabled system_compliance_topic_enabled; do
        opsbro agent parameters set $param false
        if [ $? != 0 ];then
           echo "ERROR: cannot set the agent parameter: $param"
           exit 2
        fi
    done
}


function assert_group {
   # If the daemon did crash, exit
   assert_no_crash

   opsbro detectors wait-group "$1"
   if [ $? != 0 ];then
       echo "ERROR: cannot find the group $1"
       cat /var/log/opsbro/daemon.log
       cat /var/log/opsbro/gossip.log
       cat /var/log/opsbro/detector.log
       cat /var/log/opsbro/hosting-driver.log
       cat /var/log/opsbro/crash.log 2>/dev/null
       ls -thor /var/log/opsbro/
       opsbro agent info
       exit 2
   fi
}


function do_bad_exit_and_logs {
    echo "ERROR: exiting because $1"
    cat /var/log/opsbro/daemon.log
    cat /var/log/opsbro/gossip.log
    cat /var/log/opsbro/detector.log
    cat /var/log/opsbro/hosting-driver.log
    cat /var/log/opsbro/key-value.log
    cat /var/log/opsbro/crash.log 2>/dev/null
    ls -thor /var/log/opsbro/
    echo "ERROR: exiting because $1"
}


function assert_my_zone_is_encrypted {
   out=$(opsbro agent info)
   if [ $? != 0 ];then
      echo "CANNOT check that the zone is ecrypted, agent info did fail: $out"
      exit 2
   fi

   echo "$out" | grep "zone have a gossip key"
   if [ $? != 0 ];then
       echo "Seems that your zone is NOT encrypted:"
       echo "$out" | grep -i zone
       exit 2
   fi
}


function assert_ping_node {
    NODE="$1"
    out=$(opsbro gossip ping $NODE)
    if [ $? != 0 ];then
       echo "ERROR: ping node $NODE did fail"
       echo "$out"
       exit 2
    fi
    echo "$out"
}

function assert_ping_fail_node {
    NODE="$1"
    out=$(opsbro gossip ping $NODE)
    if [ $? == 0 ];then
       echo "ERROR: CAN ping node $NODE and should NOT"
       echo "$out"
       exit 2
    fi
    echo "$out"
}


function assert_public_addr_range {
    RANGE=$1
    my_public_ip=$(opsbro agent print public-addr)
    out=$(opsbro evaluator wait-eval-true "ip_is_in_range('$my_public_ip', '$RANGE')" --timeout=10)
    if [ $? != 0 ];then
       echo "ERROR: our public IP $my_public_ip is not in the good range $RANGE"
       echo "$out"
       exit 2
    fi
    echo "OK: our public IP $my_public_ip is in the good range $RANGE"
}

function assert_local_addr_range {
    RANGE=$1
    my_local_ip=$(opsbro agent print local-addr)
    out=$(opsbro evaluator wait-eval-true "ip_is_in_range('$my_local_ip', '$RANGE')" --timeout=10)
    if [ $? != 0 ];then
       echo "ERROR: our local IP $my_local_ip is not in the good range $RANGE"
       echo "$out"
       exit 2
    fi
    echo "OK: our local IP $my_local_ip is in the good range $RANGE"
}


function get_other_node_addr {
   OTHER="$1"
   opsbro evaluator eval "get_other_node_address('$OTHER')" --short
   if [ $? != 0 ];then
       echo "ERROR: cannot find the other node $OTHER address"
       exit 2
    fi
}

function assert_addr_in_range {
    ADDR="$1"
    RANGE="$2"
    echo "EVAL: ip_is_in_range('$ADDR', '$RANGE')"
    out=$(opsbro evaluator wait-eval-true "ip_is_in_range('$ADDR', '$RANGE')" --timeout=10)
    if [ $? != 0 ];then
       echo "ERROR: the address $ADDR is not in the good range $RANGE"
       echo "$out"
       exit 2
    fi
    echo "OK: The address $ADDR is in the good range $RANGE"
}



function assert_one_package_can_be_installed_and_detected {
    TEST_PACKAGE_NAME="$1"
    echo "We should not have the $TEST_PACKAGE_NAME package installed"

    MASSIVE_INSTALL_LOG=/tmp/massive_install_test
    > $MASSIVE_INSTALL_LOG
    /dnf_remove     $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG
    /yum_remove     $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG
    /apt_get_remove $TEST_PACKAGE_NAME >>$MASSIVE_INSTALL_LOG  2>>$MASSIVE_INSTALL_LOG


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
       cat /var/log/opsbro/*system-packages*log
       ps axjf
       exit 2
    fi
}