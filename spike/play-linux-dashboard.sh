#!/usr/bin/env bash

which wget 2>/dev/null >/dev/null
if [ $? != 0 ]; then
   echo " * Note: Missing the wget command, installing it"
   apt-get update >/dev/null 2>/dev/null && apt-get install -y wget >/dev/null 2>/dev/null
   yum  --nogpgcheck  -y  --rpmverbosity=error  --errorlevel=1  --color=auto install wget  2>/dev/null
fi

which unzip 2>/dev/null >/dev/null
if [ $? != 0 ]; then
   echo " * Note: Missing the unzip command, installing it"
   apt-get update >/dev/null 2>/dev/null && apt-get install -y unzip >/dev/null 2>/dev/null
   yum  --nogpgcheck  -y  --rpmverbosity=error  --errorlevel=1  --color=auto install unzip  2>/dev/null
fi


# We try to find the LAST possible Python VERSION
pythonver() {
    versions="2.6 2.7"
    LASTFOUND=""
    # Is there any python here?
    for v in $versions
    do
        which python$v > /dev/null 2>&1
        if [ $? -eq 0 ]
        then
            LASTFOUND="python$v"
        fi
    done
    if [ -z "$LASTFOUND" ]
    then
        # Finaly try to find a default python
        which python > /dev/null 2>&1
        if [ $? -ne 0 ]
        then
            # Beware: maybe it's because which is not exiting itself! (like in docker centos images)
            if [ -f "/usr/bin/python" ]; then
                LASTFOUND="/usr/bin/python"
            else
                echo "No python2 interpreter found!"
                exit 2
            fi
        else
            echo "python found"
            LASTFOUND=$(which python)
        fi
    fi
    PYTHON=$LASTFOUND
}

# Ok, go search this Python version
pythonver


if [ $? == 0 ];then
  echo "Getting the OpsBro source from github"
  wget https://github.com/naparuba/opsbro/archive/master.zip --output-document /tmp/opsbro-master.zip >/dev/null 2>/dev/null
  cd /tmp
  unzip /tmp/opsbro-master.zip >/dev/null 2>/dev/null
  cd opsbro-master
fi




echo "All is OK, launching the dashboard"
sleep 2

LANG=en_US.UTF8 $PYTHON -u bin/opsbro dashboards show linux

printf "Demo is finish, OpsBro is able of far more than just a dashboard, more to come in the documentation very soon (⌐■_■)\n"
sleep 2

python bin/opsbro banner

printf "Shinken Solutions Team is working on a great monitoring solution: Shinken Enterprise. Have a look if you need a powerful monitoring (/.__.)/ \(.__.\)\n"

