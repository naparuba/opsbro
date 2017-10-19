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
                echo "No python interpreter found!"
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


echo "FOUND PYTHON $PYTHON"



LANG=en_US.UTF8 $PYTHON -u bin/opsbro dashboards show linux


