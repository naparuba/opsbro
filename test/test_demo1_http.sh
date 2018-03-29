#!/usr/bin/env bash

CASE=$1


# Set a valid display name for debug
opsbro agent parameters set display_name "$CASE"


# Haproxy is the central node, it will ensure us that all nodes will talk togethers
if [ $CASE == "NODE-HAPROXY" ]; then
   opsbro agent parameters set proxy-node true
   opsbro agent parameters add groups demo_haproxy
fi


# Client node will need to expose nodes with DNS
if [ $CASE == "NODE-CLIENT" ]; then
   opsbro packs overload global.dns
   opsbro packs parameters set local.dns.port  53
   opsbro agent parameters add groups dns-listener
   printf "nameserver 127.0.0.1\n" > /etc/resolv.conf
fi


# We are ready, launch the whole daemons
/etc/init.d/opsbro start

# For debug purpose
ip addr show | grep 'scope global'


sleep 60


# Let the nodes join them selve.
# NOTE: the haproxy node will be slower to get here, because he need to install haproxy during the start
opsbro gossip detect --auto-join

echo "Sleeping while others nodes pop up too"
sleep 30

MEMBERS=$(opsbro gossip members)

NB_MEMBERS=$(echo "$MEMBERS" | grep 'docker-container' | wc -l)

# Must have all 4 nodes available
if [ $NB_MEMBERS != 4 ]; then
   echo "BAD number of members: $NB_MEMBERS"
   echo "$MEMBERS"
   cat /var/log/opsbro/gossip.log
   exit 2
fi


# Check that HTTP nodes are running well
if [ $CASE == "NODE-HTTP-1" ] || [ $CASE == "NODE-HTTP-2" ]; then
   PAYLOAD=$(curl -s http://localhost/)
   echo "PAYLOAD $PAYLOAD"
   if [ "$PAYLOAD" != "$CASE" ]; then
      echo "ERROR: the http page is not ready"
      exit 2
   fi

   # They must have the apache group
   opsbro detectors wait-group 'apache'
   if [ $? != 0 ];then
      echo "ERROR: the apache group was not detected"
      exit 2
   fi

   echo "$CASE will wait for queries"
   sleep 120

   echo "Finish, exiting"
   exit 0
fi


# Haproxy compliance must have installed the haproxy package
if [ $CASE == "NODE-HAPROXY" ]; then
    opsbro compliance wait-compliant "TEST HAPROXY" --timeout=60
    if [ $? != 0 ]; then
        echo "Haproxy compliance cannot be fixed in COMPLIANCE state in 60s"
        opsbro compliance state
        exit 2
    fi

    echo "Compliance history that did install HAPROXY"
    opsbro compliance state


    echo "The haproxy group should now be detected"
    opsbro detectors wait-group 'haproxy'
    if [ $? != 0 ];then
       echo "ERROR: the haproxy group was not detected"
       exit 2
    fi


    echo "Testing local proxying"
    /etc/init.d/haproxy status | grep 'haproxy is running'
    if [ $? != 0 ];then
       echo "ERROR: the haproxy daemon is not running"
       cat /var/log/opsbro/generator.log
       exit 2
    fi

    OUT=$(curl -s http://localhost)
    if [[ "$OUT" != "NODE-HTTP-1" ]] && [[ "$OUT" != "NODE-HTTP-2" ]]; then
         echo "Cannot reach real HTTP servers from the local HAPROXY: $OUT"
         cat /var/log/opsbro/generator.log
         exit 2
    fi


    grep 'NODE-HTTP-2' /etc/haproxy/haproxy.cfg > /dev/null
    if [ $? != 0 ];then
       echo "ERROR: cannot find the NODE-HTTP-2 in the haproxy configuration"
       cat /etc/haproxy/haproxy.cfg
       exit 2
    fi
    grep 'NODE-HTTP-1' /etc/haproxy/haproxy.cfg > /dev/null
    if [ $? != 0 ];then
       echo "ERROR: cannot find the NODE-HTTP-1 in the haproxy configuration"
       cat /etc/haproxy/haproxy.cfg
       exit 2
    fi

    echo "Haproxy stats"
    STATS=$(curl -s "http://admin:admin@localhost/stats;csv;norefresh")
    NB=$(echo "$STATS" | grep 'back_http' | grep -v BACKEND | wc -l)
    if [ "$NB" != "2" ];then
       echo "Bad total number of back http in haproxy $NB"
       echo "$STATS"
       exit 2
    fi

    NB_UP=$(echo "$STATS" | grep 'back_http' | grep -v BACKEND | grep UP | wc -l)
    if [ "$NB" != "2" ];then
       echo "Bad number of back http in haproxy in UP $NB"
       echo "$STATS"
       exit 2
    fi


    echo "HAPROXY node will wait for client queries"
    sleep 120
    echo "HAPROXY node exiting"
fi



if [ $CASE == "NODE-CLIENT" ]; then

   # Trying to curl all IPS just for debug purpose
   for ii in `seq 1 6`; do
      echo " - Trying http://172.17.0.$ii"
      curl http://172.17.0.$ii
      echo ""
   done

   echo "try to detect haproxy address"
   dig -p 6766  @127.0.0.1 haproxy.group.local.opsbro

   dig haproxy.group.local.opsbro +short A

   ping -c 1 haproxy.group.local.opsbro
   if [ $? != 0 ];then
       echo "ERROR: cannot ping the haproxy node"
       exit 2
   fi

   printf "\n\n\n************************* Checking HTTP proxying **************************\n"
   TOTAL=50
   for ii in `seq 1 $TOTAL`; do
      printf "\r→ "
      sync
      OUT=$(curl -s http://haproxy.group.local.opsbro)
      if [[ "$OUT" != "NODE-HTTP-1" ]] && [[ "$OUT" != "NODE-HTTP-2" ]]; then
         echo "Cannot reach real HTTP servers from the client: $OUT"
         exit 2
      fi
      printf "$OUT %d/%d" $ii $TOTAL
      sleep 0.2
   done
   printf "\n"
   echo "Test IS full OK, we did reach our servers"
   exit 0
fi

# This should be not executed
echo "UNKNOWN NODE"
exit 2

