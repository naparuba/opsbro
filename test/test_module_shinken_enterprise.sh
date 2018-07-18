#!/usr/bin/env bash

. test/common_shell_functions.sh



print_header "Starting to test Shinken Enterprise module"


print_header "Configuring"
python -u bin/opsbro packs overload global.shinken-enterprise
python -u bin/opsbro packs parameters set local.shinken-enterprise.enabled True
python -u bin/opsbro packs parameters set local.shinken-enterprise.file_result "/tmp/shinken-local-analyzer-payload.json"

# Be sure to disable websocket, we do not want it
python -u bin/opsbro packs overload global.websocket
python -u bin/opsbro packs parameters set local.websocket.enabled False



print_header "Launch"

# Launch the agent in a one-shot mode (not a daemon, only one loop)
# Timeout after 125s (120 from the ssh + 5s bonus so the timeout will be the ssh one)
# NOTE: --preserve-status => cannot be used because centos6 do not have it
# --signal=9 => when timeout, just kill it and all it's sons
timeout --signal=9 125s python -u bin/opsbro agent start --one-shot


print_header "Look at final result"
cat /tmp/shinken-local-analyzer-payload.json | jq
if [ $? != 0 ];then
   echo "ERROR: the json file seems to be invalid or missing"
   exit 2
fi



# NOTE: bash: no " around the for string"
for key in use _LAT _LONG _FQDN _TIMEZONE _LINUX_DISTRIBUTION host_name address _AGENT_UUID _VOLUMES; do
   echo "    - key: $key"
   cat /tmp/shinken-local-analyzer-payload.json | jq ".$key"
   if [ $? != 0 ];then
      echo "ERROR: the json file seems to be invalid or missing"
      cat log/module.*.log
      exit 2
   fi
   echo ""
done


print_header "Done"
echo "opsbro Shinken Enterprise module is OK"
