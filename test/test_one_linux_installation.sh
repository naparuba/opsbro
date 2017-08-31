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


sleep 60


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Info           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
opsbro agent info
if [ $? != 0 ]; then
   echo "ERROR: information get failed!"
   cat /var/log/opsbro/daemon.log
   exit 2
fi

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Address?       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Is there an address used by the daemon?
ADDR=$(opsbro agent info | grep Addr | awk '{print $2}')
if [ "$ADDR" == "None" ]; then
   echo "The opsbro daemon do not have a valid address."
   echo `opsbro agent info`
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Linux TAG      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if linux tag is set
test/assert_tag.sh "linux"
if [ $? != 0 ]; then
   echo "ERROR: the tag linux is missing!"
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Docker-container TAG      ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Check if docker-container tag is set
test/assert_tag.sh "docker-container"
if [ $? != 0 ]; then
   echo "ERROR: the tag docker-container is missing!"
   exit 2
fi
