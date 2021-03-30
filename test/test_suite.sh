#!/usr/bin/env bash

echo "##################### Launching TEST $TEST_SUITE on $TRAVIS_OS_NAME"

# no sudo on windows
if [ "$TRAVIS_OS_NAME" == "windows" ];then
   SUDO=""

   echo "COPY TO c:\opsbro"
   mkdir 'c:\opsbro'
   cp -rp . 'c:\opsbro'
   ls "c:\opsbro"
   python 'bin/opsbro'
   python 'bin/opsbro' agent start --one-shot
   echo "Analyser RUN"
   python 'bin/opsbro' packs overload   global.shinken-enterprise
   python 'bin/opsbro' packs parameters set local.shinken-enterprise.enabled True
   python 'bin/opsbro' packs parameters set local.shinken-enterprise.file_result "C:\shinken-local-analyzer-payload.json"
   python 'bin/opsbro' agent start --one-shot
   type 'C:\shinken-local-analyzer-payload.json'

   echo "SERVICE RUN"
   "python -c \"import sys; print(sys.executable)\""
   # clean all logs
   wevtutil cl System
   wevtutil cl Application
   python c:/opsbro/bin/opsbro agent windows service-install
   sc start OpsBro || sc qc OpsBro && sc query OpsBro && wevtutil qe Application && wevtutil qe System && type c:\opsbro.log && bad

   echo "Other commands"
   python -c "import time; time.sleep(10)"
   python c:/opsbro/bin/opsbro agent info
   python c:/opsbro/bin/opsbro collectors state
   python c:/opsbro/bin/opsbro monitoring state
   python c:/opsbro/bin/opsbro compliance state
   python c:/opsbro/bin/opsbro collectors show
   sc stop OpsBro

   exit 0
else
   SUDO="sudo"
fi

# Always be sure we are loggued in docker
if [ ! -f /root/.docker/config.json ]; then
   echo "Login to docker with credentials naparuba"
   if [ "X$DOCKER_TOKEN" == "X" ]; then
      echo "WARNING: Your docker token is void!"
   fi
   docker login --username naparuba --password "$DOCKER_TOKEN"
fi

# Look if we did set our docker env variables, for some tests
if [ ! -f ~/.docker_env ]; then
   printf "DISCORD_TOKEN=$DISCORD_TOKEN\nDISCORD_CHANNEL=$DISCORD_CHANNEL\n" >~/.docker_env
fi
#--env-file ~/.docker_env

# Travis: only need to run the installation once, it it not link to a specific python version. They don't need to use CPU for nothing ;)
if [ "$TEST_SUITE" == "PYTHON" ]; then
   # No more virtual env on Travis
   $SUDO rm -fr ~/virtualenv
   echo "Installing opsbro for TESTING (so have libs)"
   cd ..
   # NOTE: sudo because travis is under ubuntu
   $SUDO python setup.py install

   # NOTE: nosetests are hooking stdout and sys.paths, and so are not in real execution, this make too much troubles
   # with tests, so switching to a real world test
   test/launch_python_tests.sh
   exit $?
fi

echo "Test installations for SUITE  $TEST_SUITE"
# If not python, launch installations, and only a sub part if possible
./test_installation.sh

exit $?
