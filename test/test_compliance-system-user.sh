#!/usr/bin/env bash

echo "Starting to test Compliance for user existence"


echo "*************** User creation *****************"

EXPECTED='shinken:x:500:500:Shinken User:/var/lib/shinken:/bin/shinken'
CAN_MOD="TRUE"
groupadd --gid 500 shinken
if [ $? != 0 ]; then
   echo "Alpine linux"
   addgroup -g 500 shinken
   CAN_MOD="FALSE"
fi
#useradd --home-dir /var/lib/shinken  --gid 500 --shell /bin/shinken --comment "Shinken User"  --uid 500 shinken


# Start daemon
/etc/init.d/opsbro start


opsbro compliance wait-compliant "USER SHINKEN"
if [ $? != 0 ]; then
  echo "ERROR: the compliance USER SHINKEN should be compliant"
  opsbro compliance state
  exit 2
fi

id shinken
if [ $? != 0 ];then
   echo "ERROR: the user shinken should exists"
fi

cat /etc/passwd
grep "$EXPECTED" /etc/passwd
if [ $? != 0 ];then
   echo "ERROR: the shinken user do not have expected properties"
   cat /etc/passwd
   exit 2
fi

if [ "$CAN_MOD"  == "TRUE" ]; then


  echo "*************** User modification *****************"
  # Now modify the user and expect the shinken user to get back to normal
  usermod --comment "Nop, pas OK" shinken
  if [ $? != 0 ];then
     echo "ERROR: seems that the usermod command did fail"
     opsbro compliance state
     exit 2
  fi


  opsbro compliance wait-compliant "USER SHINKEN"
  if [ $? != 0 ]; then
    echo "ERROR: the compliance USER SHINKEN should be compliant after a fixed"
    opsbro compliance state
    exit 2
  fi
fi


printf "\n ****** Result ***** \n"
echo "OK:  Compliance in enforcing mode is working"
