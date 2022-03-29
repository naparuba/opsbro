#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test Shinken Enterprise module"

print_header "Configuring"
$PYTHON_EXE -u bin/opsbro packs overload global.shinken-enterprise
$PYTHON_EXE -u bin/opsbro packs parameters set local.shinken-enterprise.enabled True
$PYTHON_EXE -u bin/opsbro packs parameters set local.shinken-enterprise.file_result "/tmp/shinken-local-analyzer-payload.json"

# Be sure to disable websocket, we do not want it
$PYTHON_EXE -u bin/opsbro packs overload global.websocket
$PYTHON_EXE -u bin/opsbro packs parameters set local.websocket.enabled False

print_header "Launch"

# Launch the agent in a one-shot mode (not a daemon, only one loop)
# Timeout after 125s (120 from the ssh + 5s bonus so the timeout will be the ssh one)
# NOTE: --preserve-status => cannot be used because centos6 do not have it
# --signal=9 => when timeout, just kill it and all it's sons
timeout --signal=9 125s $PYTHON_EXE -u bin/opsbro agent start --one-shot

print_header "Look at final result"
cat /tmp/shinken-local-analyzer-payload.json
if [ $? != 0 ]; then
   echo "ERROR: the json file seems to be invalid or missing"
   ls -thor log
   cat log/module.*.log
   cat log/daemon.log
   cat log/crash.log
   exit 2
fi

# NOTE: bash: no " around the for string"
for key in use _LAT _LONG _FQDN _TIMEZONE _LINUX_DISTRIBUTION host_name address _AGENT_UUID _VOLUMES; do
   echo "    - key: $key"
   cat /tmp/shinken-local-analyzer-payload.json | jq ".$key"
   if [ $? != 0 ]; then
      echo "ERROR: the json file seems to be invalid or missing"
      cat log/module.*.log
      exit 2
   fi
   echo ""
done

exit_if_no_crash "opsbro Shinken Enterprise module is OK"
