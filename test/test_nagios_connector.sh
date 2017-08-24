#!/usr/bin/env bash


echo "Starting to test Nagios export (dummy check)"



/etc/init.d/opsbro start

# It will restart nagios
sleep 10

/etc/init.d/opsbro stop

sleep 5

/etc/init.d/opsbro start

sleep 10

/usr/local/nagios/bin/nagios -v /usr/local/nagios/etc/nagios.cfg

ls -R /usr/local/nagios/etc/

# Start opsbro and assert that the cfg file of the local element is created
NB_CFG=$(ls -1 /usr/local/nagios/etc/objects/agent/*cfg | wc -l)


if [ $NB_CFG == 0 ]; then
    echo "ERROR: the cfg file for nagios was not created!"
    exit 2
fi

# Nagios check should be OK
NAGIOS_CHECK=$(/usr/local/nagios/bin/nagios -v /usr/local/nagios/etc/nagios.cfg)

if [ $? != 0 ]; then
    echo "ERROR: the nagios check is not happy"
    printf "%s" "$NAGIOS_CHECK"
    exit 2
fi


# There sould be some alerts now in nagios log
EXPORTED_CHECKS=$(cat  /usr/local/nagios/var/nagios.log | grep 'SERVICE ALERT' | grep Agent-dummy | wc -l)

if [ $EXPORTED_CHECKS == 0 ]; then
    echo "ERROR: the checks executions are not send into nagios"
    cat  /usr/local/nagios/var/nagios.log
    exit 2
fi

echo "OK:  nagios cfg export is working as expected (node is exported into CFG and checks are launched and received by Nagios"
