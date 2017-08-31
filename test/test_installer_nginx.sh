#!/usr/bin/env bash


test/assert_tag.sh "nginx" >/dev/null 2>/dev/null
if [ $? == 0 ]; then
    echo "ERROR: nginx tag should NOT be set"
    exit 2
fi

# Activate the installer
touch /tmp/install_nginx

# Wait a bit in order to allow opsbro to install it (and wiaht for package, etc etc)
sleep 30

test/assert_tag.sh "nginx"
if [ $? != 0 ]; then
    echo "ERROR: nginx tag should be set"
    exit 2
fi


opsbro agent info | grep Tags
echo "Nginx installer is OK"


