#!/usr/bin/env bash


# Travis: only need to run the installation once, it it not link to a specific python version. They don't need to use CPU for nothing ;)
if [ "$TEST_SUITE" == "PYTHON" ]; then
   echo "Test launch for Python"
   nosetests -xv --processes=1 --process-timeout=300 --process-restartworker --with-cov --cov=opsbro --exe
   exit $?
fi

echo "Test installations for SUITE  $TEST_SUITE"
# If not python, launch installations, and only a sub part if possible
./test_installation.sh

exit $?