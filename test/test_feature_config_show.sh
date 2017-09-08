#!/usr/bin/env bash

echo "Starting to test agent parameters show"

opsbro agent parameters show

if [ $? != 0 ]; then
    echo "The opsbro agent parameters show show did fail"
    exit 2
fi


echo "opsbro agent parameters show OK"
