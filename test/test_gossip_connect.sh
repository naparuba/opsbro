#!/usr/bin/env bash

NODE_NB=$1

/etc/init.d/opsbro start

# Wait for other dockers to be spawned
sleep 10

# Sleep a bit to be sure that node2 is up and ready to answer us
#sleep 120
ip addr show | grep eth0


# Node 1 ip=2
if [ "$NODE_NB" == "1" ]; then
  opsbro gossip join 172.17.0.2
  opsbro gossip join 172.17.0.3
fi

# Node 2 ip=3
if [ "$NODE_NB" == "2" ]; then
  opsbro gossip join 172.17.0.3
  opsbro gossip join 172.17.0.4
fi


# Node 3 ip=4
if [ "$NODE_NB" == "2" ]; then
  opsbro gossip join 172.17.0.4
  opsbro gossip join 172.17.0.5
fi

sleep 10
echo "Waiting done, everyone should be there"

opsbro gossip members


NB_MEMBERS=$(opsbro gossip members | grep 'docker-container' | wc -l)

if [ $NB_MEMBERS != 3 ]; then
   echo "BAD number of members: $NB_MEMBERS"
   cat /var/log/opsbro/gossip.log
   exit 2
fi

# let the others finish
sleep 30

echo "Gossip join is OK"


