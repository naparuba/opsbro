#!/usr/bin/env bash


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
  rm -fr /tmp/opsbro.tar.gz /tmp/opsbro
  curl -s http://linux.dashboard.static.opsbro.io/opsbro.tar.gz > /tmp/opsbro.tar.gz
  cd /tmp
  tar xfz opsbro.tar.gz
  cd opsbro
fi




echo "All is OK, launching the dashboard"
sleep 2

LANG=en_US.UTF8 $PYTHON -u bin/opsbro dashboards show linux
if [ $? != 0 ]; then
   echo "Oups, something get wrong on the agent start, please report it at the github issues (https://github.com/naparuba/opsbro/issues)"
   exit 2
fi

printf "Demo is finish, OpsBro is able of far more than just a dashboard, more to come in the documentation very soon (⌐■_■)\n"
sleep 2

python bin/opsbro banner

printf "Shinken Solutions Team is working on a great monitoring solution: Shinken Enterprise. Have a look if you need a powerful monitoring (/.__.)/ \(.__.\)\n"

