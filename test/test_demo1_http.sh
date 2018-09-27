#!/usr/bin/env bash

# We are now a WAN based node
#test/set_network_simulated_type WAN

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

CASE=$1

ping -c 1 http1
ping -c 1 http2
ping -c 1 haproxy
ping -c 1 client


printf "\n\n"
echo "============================== [`date`] Configuration setup ================================="



function wait_step_event {
    echo " * Waiting for other nodes events. Starts at `date`"
    wait_event_with_timeout "$1-NODE-HTTP-1" 180
    wait_event_with_timeout "$1-NODE-HTTP-2" 180
    wait_event_with_timeout "$1-NODE-HAPROXY" 180
    wait_event_with_timeout "$1-NODE-CLIENT" 180
}

print_header "$CASE starts to run `date` $TRAVIS"


# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"


# Haproxy is the central node, it will ensure us that all nodes will talk togethers
if [ $CASE == "NODE-HAPROXY" ]; then
   opsbro agent parameters set proxy-node true
   opsbro agent parameters add groups demo_haproxy
fi


# Client node will need to expose nodes with DNS, and use the standard way to hook dns queries
if [ $CASE == "NODE-CLIENT" ]; then
   opsbro agent parameters add groups dns-listener

   print_header "Wait for dns relay"
   opsbro compliance wait-compliant "Install local dns relay" --timeout=60
   if [ $? != 0 ];then
      echo "ERROR: the local dns cannot be installed"
      opsbro generators state
      opsbro generators history
      cat /var/log/opsbro/generator.log
      cat /var/log/opsbro/crash.log 2>/dev/null
   fi
fi


# We are ready, launch the whole daemons
printf "\n\n"
echo "============================== [`date`] Launching daemon ================================="
/etc/init.d/opsbro start

echo "Daemon started `date`"

opsbro agent info
if [ $? != 0 ];then
   echo "ERROR: `date` the daemon was not started"
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   exit 2
fi

# For debug purpose
show_my_system_ip




# Let the nodes join them selve.
# NOTE: the haproxy node will be slower to get here, because he need to install haproxy during the start
echo "Launching UDP detection `date`"
opsbro gossip detect --auto-join --timeout=15
if [ $? != 0 ];then
   echo "ERROR: `date` the automatic detect call did fail after 15s"
   cat /var/log/opsbro/gossip.log
   cat /var/log/opsbro/daemon.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   exit 2
fi



printf "\n\n"
echo "============================== [`date`] STEP1 synchronization ================================="
echo "Adding my own event: STEP1-$CASE  at `date`"

opsbro gossip events add  "STEP1-$CASE"
wait_step_event "STEP1"

echo "All nodes are syncronized at `date`"





printf "\n\n"
echo "============================== [`date`] Checking we are 4 members ================================="

# We must have all nodes now
wait_member_display_name_with_timeout "NODE-HTTP-1" 10
wait_member_display_name_with_timeout "NODE-HTTP-2" 10
wait_member_display_name_with_timeout "NODE-HAPROXY" 10
wait_member_display_name_with_timeout "NODE-CLIENT" 10



# Check that HTTP nodes are running well
if [ $CASE == "NODE-HTTP-1" ] || [ $CASE == "NODE-HTTP-2" ]; then

   printf "\n\n"
   echo "============================== [`date`] $CASE apache checking ================================="

   PAYLOAD=$(curl -s http://localhost/)
   echo "PAYLOAD $PAYLOAD"
   if [ "$PAYLOAD" != "$CASE" ]; then
      echo "ERROR: `date` the http page is not ready"
      exit 2
   fi

   # They must have the apache group
   opsbro detectors wait-group 'apache'
   if [ $? != 0 ];then
      echo "ERROR:  `date` the apache group was not detected"
      exit 2
   fi

   # Let the httproxy node know we are ready for checking the haproxy state
   opsbro gossip events add  "HTTP-READY-$CASE"

   echo "$CASE  `date` will wait for queries until all others nodes are done"

   opsbro gossip events add  "ENDING-$CASE"
   if [ $? != 0 ];then
      echo "ERROR: cannot send a event ENDING-$CASE"
      cat /var/log/opsbro/daemon.log
      cat /var/log/opsbro/gossip.log
      cat /var/log/opsbro/crash.log 2>/dev/null
      exit 2
   fi
   wait_step_event "ENDING"


   echo "$CASE exiting at `date`"
   exit 0
fi


# Haproxy compliance must have installed the haproxy package
if [ $CASE == "NODE-HAPROXY" ]; then

    printf "\n\n"
    echo "============================== [`date`] $CASE waiting for HTTP node to be ready ================================="

    ps axjf


    # Wait until the http-1 and http-2 are ready to be queried
    wait_event_with_timeout "HTTP-READY-NODE-HTTP-1" 180
    wait_event_with_timeout "HTTP-READY-NODE-HTTP-2" 180


    printf "\n\n"
    echo "============================== [`date`] $CASE checking that haproxy is happy ================================="
    echo "HAPROXY: look to see if haproxy is installed  `date`"
    opsbro compliance wait-compliant "TEST HAPROXY" --timeout=60
    if [ $? != 0 ]; then
        echo "Haproxy compliance cannot be fixed in COMPLIANCE state in 60s"
        opsbro compliance state
        exit 2
    fi

    echo "Compliance history that did install HAPROXY   `date`"
    opsbro compliance state


    echo "The haproxy group should now be detected"
    opsbro detectors wait-group 'haproxy'
    if [ $? != 0 ];then
       echo "ERROR: the haproxy group was not detected"
       cat /var/log/opsbro/crash.log 2>/dev/null
       exit 2
    fi


    echo "Testing local proxying"
    /etc/init.d/haproxy status | grep 'haproxy is running'
    if [ $? != 0 ];then
       # Maybe it's being restarted
       sleep 2
       /etc/init.d/haproxy status | grep 'haproxy is running'
       if [ $? != 0 ];then  # OK really dead now
          echo "ERROR: `date` the haproxy daemon is not running"
          /etc/init.d/haproxy status
          ps axjf
          cat /var/log/opsbro/generator.log
          cat /etc/haproxy/haproxy.cfg
          cat /var/log/opsbro/crash.log 2>/dev/null
          exit 2
       fi
    fi

    ls -thor /var/log
    ls -thor /var/log/haproxy
    cat /var/log/haproxy*
    cat /var/log/haproxy/*
    cat /var/log/messages

    ps axjf

    opsbro generators history
    opsbro generators state
    opsbro generators wait-compliant haproxy
    if [ $? != 0 ];then
       echo "ERROR: cannot have the haproxy generator as compliant"
       exit 2
    fi

    echo "HAPROXY: look if local proxying is valid  `date`"
    OUT=$(curl -s http://localhost)
    if [[ "$OUT" != "NODE-HTTP-1" ]] && [[ "$OUT" != "NODE-HTTP-2" ]]; then
         echo "HAPROXY `date` Cannot reach real HTTP servers from the local HAPROXY: $OUT"
         cat /var/log/opsbro/generator.log
         cat /etc/haproxy/haproxy.cfg
         cat /var/log/opsbro/crash.log 2>/dev/null
         exit 2
    fi

    ps axjf

    grep 'NODE-HTTP-2' /etc/haproxy/haproxy.cfg > /dev/null
    if [ $? != 0 ];then
       echo "ERROR: cannot find the NODE-HTTP-2 in the haproxy configuration"
       cat /etc/haproxy/haproxy.cfg
       exit 2
    fi
    echo "HAPROXY: `date` NODE-HTTP-2 is present"

    ps axjf

    grep 'NODE-HTTP-1' /etc/haproxy/haproxy.cfg > /dev/null
    if [ $? != 0 ];then
       echo "ERROR: cannot find the NODE-HTTP-1 in the haproxy configuration"
       cat /etc/haproxy/haproxy.cfg
       exit 2
    fi
    echo "HAPROXY: `date` NODE-HTTP-1 is present"

    echo "Haproxy stats"
    STATS=$(curl -s "http://admin:admin@localhost/stats;csv;norefresh")
    NB=$(echo "$STATS" | grep 'back_http' | grep -v BACKEND | wc -l)
    if [ "$NB" != "2" ];then
       echo "ERROR: Bad total number of back http in haproxy $NB"
       echo "$STATS"
       cat /var/log/opsbro/generator.log
       cat /etc/haproxy/haproxy.cfg
       cat /var/log/opsbro/crash.log 2>/dev/null
       exit 2
    fi

    ps axjf

    NB_UP=$(echo "$STATS" | grep 'back_http' | grep -v BACKEND | grep UP | wc -l)
    if [ "$NB" != "2" ];then
       echo "Bad number of back http in haproxy in UP $NB"
       echo "$STATS"
       exit 2
    fi


    printf "\n\n"
    echo "============================== [`date`] $CASE let the client know we are ready ================================="
    # Let the httproxy node know we are ready for checking the haproxy state
    opsbro gossip events add  "LB-READY-$CASE"

    printf "\n\n"
    echo "============================== [`date`] $CASE waiting for end ================================="

    opsbro gossip events add  "ENDING-$CASE"
    wait_step_event "ENDING"

    echo "$CASE node exiting  `date`"
    exit 0
fi



if [ $CASE == "NODE-CLIENT" ]; then

   printf "\n\n"
   echo "============================== [`date`] $CASE waiting until the Load balancing is ready ================================="

   # Wait until the http-1 and http-2 are ready to be queried
   wait_event_with_timeout "LB-READY-NODE-HAPROXY" 180


   printf "\n\n"
   echo "============================== [`date`] $CASE checking direct URI and the Load balancing  ================================="

   for ii in `seq 1 6`; do
      echo " - Trying http://172.17.0.$ii"
      curl -s --connect-timeout 4 http://172.17.0.$ii
      echo ""
   done

   echo "CLIENT:  `date` try to detect haproxy address"
   dig haproxy.group.local.opsbro +short A

   ping -c 1 haproxy.group.local.opsbro
   if [ $? != 0 ];then
       echo "ERROR: cannot ping the haproxy node"
       exit 2
   fi


   TOTAL=20
   for ii in `seq 1 $TOTAL`; do
      printf "\r→ "
      sync
      OUT=$(curl --connect-timeout 4 -s http://haproxy.group.local.opsbro)
      if [[ "$OUT" != "NODE-HTTP-1" ]] && [[ "$OUT" != "NODE-HTTP-2" ]]; then
         # Maybe the haproxy is restarting, try one more time
         sleep 1
         OUT=$(curl --connect-timeout 4 -s http://haproxy.group.local.opsbro)
         if [[ "$OUT" != "NODE-HTTP-1" ]] && [[ "$OUT" != "NODE-HTTP-2" ]]; then
            echo "CLIENT (test $ii/$TOTAL) Cannot reach real HTTP servers from the client: Result:====> $OUT <======"
            echo "  Launching in verbose mode:"
            curl -v http://haproxy.group.local.opsbro
            exit 2
         fi
      fi
      printf "$OUT %d/%d" $ii $TOTAL
      sleep 0.2
   done
   printf "\n"
   echo "CLIENT  `date` Test IS full OK, we did reach our servers"


   printf "\n\n"
   echo "============================== [`date`] $CASE waiting for others node to ends ================================="

   opsbro gossip events add  "ENDING-$CASE"
   wait_step_event "ENDING"

   exit 0
fi

# This should be not executed
echo "UNKNOWN NODE"
exit 2


