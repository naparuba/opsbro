#!/usr/bin/env bash

echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Installation   ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
python setup.py install

if [ $? != 0 ]; then
   echo "ERROR: installation failed!"
   exit 2
fi


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Starting       ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
# Try to start daemon
/etc/init.d/kunai start
if [ $? != 0 ]; then
   echo "ERROR: daemon start failed!"
   exit 2
fi


sleep 15


echo "************** ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪   Info           ♪┏(°.°)┛┗(°.°)┓┗(°.°)┛┏(°.°)┓ ♪  *************************"
kunai info
if [ $? != 0 ]; then
   echo "ERROR: information get failed!"
   cat /var/log/kunai/daemon.log
   exit 2
fi

ADDR=$(kunai info | grep Addr | awk '{print $2}')
if [ "$ADDR" == "None" ]; then
   echo "The kunai daemon do not have a valid address."
   echo `kunai info`
   exit 2
fi