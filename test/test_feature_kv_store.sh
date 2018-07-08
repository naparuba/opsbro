#!/usr/bin/env bash

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
   exit 2
fi

echo $VALUE

echo "$VALUE" | grep pack_name
if [ $? != 0 ];then
   echo "ERROR: the VALUE seems void"
   echo $VALUE
   exit 2
fi

echo "OK: CLI kv store"
