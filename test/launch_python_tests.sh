#!/bin/bash

cd test

echo "   *********   Python unitary tests  ***********"

for ii in `ls -1 test_*py`; do
    printf " - %-50s" "$ii"
    OUTPUT=$(python $ii 2>&1)
    if [ $? != 0 ];then
        echo ""
        echo "TEST: $ii FAIL:"
        echo "$OUTPUT"
        exit 2
    fi
    printf "OK\n"
done


echo "   ******  All tests are OK   ******"
exit 0