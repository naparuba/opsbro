#!/usr/bin/env bash

echo "##################### Launching TEST $TEST_SUITE on $TRAVIS_OS_NAME"

# no sudo on windows
if [ "$TRAVIS_OS_NAME" == "windows" ];then
   SUDO=""
   # we were in test
   cd ..
   echo "COPY TO c:\opsbro"
   mkdir 'c:\opsbro'
   cp -rp . 'c:\opsbro'
   ls "c:\opsbro"
   python3 'bin/opsbro'
   python3 'bin/opsbro' agent start --one-shot
   echo "Analyser RUN"
   python3 'bin/opsbro' packs overload   global.shinken-enterprise
   python3 'bin/opsbro' packs parameters set local.shinken-enterprise.enabled True
   python3 'bin/opsbro' packs parameters set local.shinken-enterprise.file_result "C:\shinken-local-analyzer-payload.json"
   python3 'bin/opsbro' agent start --one-shot
   ls 'c:'
   cat 'C:\shinken-local-analyzer-payload.json'

   echo "SERVICE RUN"
   python3 -c "import sys; print(sys.executable)"
   # clean all logs
   wevtutil cl System
   wevtutil cl Application

   python3 setup.py install

   python3 c:/opsbro/bin/opsbro agent windows service-install
   sc start OpsBro
   sc qc OpsBro
   sc query OpsBro
   wevtutil qe Application
   wevtutil qe System

   # ls -R 'c:\opsbro\'
   echo "LOG"
   cat 'c:\opsbro.log'
   exit 2
   echo "Other commands"
   python3 -c "import time; time.sleep(10)"
   python3 c:/opsbro/bin/opsbro agent info
   python3 c:/opsbro/bin/opsbro collectors state
   python3 c:/opsbro/bin/opsbro monitoring state
   python3 c:/opsbro/bin/opsbro compliance state
   python3 c:/opsbro/bin/opsbro collectors show
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

echo "Test installations for SUITE  $TEST_SUITE"
# If not python, launch installations, and only a sub part if possible
./test_installation.sh

exit $?
