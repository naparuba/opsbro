#!/usr/bin/env bash

echo "##################### Launching TEST $TEST_SUITE"

# Always be sure we are loggued in docker
if  [ ! -f /root/.docker/config.json ]; then
    echo "Login to docker with credentials naparuba"
    if [ "X$DOCKER_TOKEN" == "X" ]; then
        echo "WARNING: Your docker token is void!"
    fi
    docker login --username  naparuba  --password  "$DOCKER_TOKEN"
fi

# Look if we did set our docker env variables, for some tests
if [ ! -f ~/.docker_env ];then
    printf "DISCORD_TOKEN=$DISCORD_TOKEN\nDISCORD_CHANNEL=$DISCORD_CHANNEL\n" > ~/.docker_env
fi
#--env-file ~/.docker_env

# Travis: only need to run the installation once, it it not link to a specific python version. They don't need to use CPU for nothing ;)
if [ "$TEST_SUITE" == "PYTHON" ]; then
   # No more virtual env on Travis
   sudo rm -fr ~/virtualenv
   echo "Installing opsbro for TESTING (so have libs)"
   cd ..
   # NOTE: sudo because travis is under ubuntu
   sudo python setup.py install

   # NOTE: nosetests are hooking stdout and sys.paths, and so are not in real execution, this make too much troubles
   # with tests, so switching to a real world test
   test/launch_python_tests.sh
   exit $?
fi


echo "Test installations for SUITE  $TEST_SUITE"
# If not python, launch installations, and only a sub part if possible
./test_installation.sh

exit $?