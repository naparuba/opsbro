#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


/etc/init.d/opsbro start

NODE_UUID=$(opsbro agent print uuid)

DISK_KEY="__health/$NODE_UUID//var/lib/opsbro/global-configuration/packs/linux/monitoring/disks"

opsbro kv-store wait-exists "$DISK_KEY"
if [ $? != 0 ];then
   echo "ERROR: the DISK key do not exists after 30s"
   exit 2
fi

VALUE=$(opsbro kv-store get "$DISK_KEY")
if [ $? != 0 ];then
   echo "ERROR: the DISK key cannot be GET"
   echo $VALUE
   exit 2
fi

echo "*********** VALUE IS ********"
echo $VALUE
echo "*****************************"

echo "GREP::"
echo $VALUE | grep -v ERROR
RES=$?
echo "::"

if [ $RES != 0 ];then
   echo "ERROR: the VALUE seems void (res=$RES)"
   echo $VALUE
   exit 2
fi

exit_if_no_crash "OK: CLI kv store"
