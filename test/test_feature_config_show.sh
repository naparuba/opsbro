#!/usr/bin/env bash

echo "Starting to test config show"

opsbro config show

if [ $? != 0 ]; then
    echo "The opsbro config show did fail"
    exit 2
fi


echo "opsbro config show OK"
