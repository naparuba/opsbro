#!/usr/bin/env bash

/etc/init.d/opsbro start

NODE_UUID=$(opsbro agent print uuid)

CPU_KEY="__health/$NODE_UUID//var/lib/opsbro/global-configuration/packs/linux/monitoring/cpu"

opsbro kv-store wait-exists "$CPU_KEY"
if [ $? != 0 ];then
   echo "ERROR: the CPU key do not exists after 30s"
   exit 2
fi

VALUE=$(opsbro kv-store get "$CPU_KEY")
if [ $? != 0 ];then
   echo "ERROR: the CPU key cannot be GET"
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
