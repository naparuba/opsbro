#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


KV_UPDATES_DIR=/var/lib/opsbro/kv_updates/

# Fake generate old updates.lst to test cleaning
print_header " Creating update files"
NOW=$(python -c 'import time;print(int(time.time()))')

TWO_WEEKS_AGO=$(python -c 'import time;print(int(time.time()) - (86400 * 15))')

mkdir $KV_UPDATES_DIR 2>/dev/null
for ii in `seq $TWO_WEEKS_AGO 60 $NOW`; do
    touch $KV_UPDATES_DIR/$ii.lst
    if [ $? != 0 ];then
        echo "ERROR: cannot create update file"
        exit 2
    fi
done


print_header " Starting daemon"
/etc/init.d/opsbro start

NODE_UUID=$(opsbro agent print uuid)

DISK_KEY="__health/$NODE_UUID//var/lib/opsbro/global-configuration/packs/linux/monitoring/disks"

print_header " Trying keys set/get"
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

opsbro agent info

if [ $RES != 0 ];then
   echo "ERROR: the VALUE seems void (res=$RES)"
   echo $VALUE
   exit 2
fi

print_header " Looking if updates files are cleaned"
# Look if the updates files are clean
if [ -f $KV_UPDATES_DIR/$TWO_WEEKS_AGO.lst ];then
    do_bad_exit_and_logs "ERROR: the update file /var/lib/opsbro/updates/$TWO_WEEKS_AGO.lst is still existing"
fi
echo "* File: /var/lib/opsbro/updates/$TWO_WEEKS_AGO.lst is cleaned"

if [ ! -f $KV_UPDATES_DIR/$NOW.lst ];then
    do_bad_exit_and_logs "ERROR: the update file /var/lib/opsbro/updates/$NOW.lst is removed!"
fi
echo "* File: /var/lib/opsbro/updates/$NOW.lst is still there"
cat /var/log/opsbro/key-value.log

exit_if_no_crash "OK: CLI kv store"
