#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


print_header "Setting values in the agent file"
# Set a valid display name for debug
opsbro agent parameters set display_name "node-1"
opsbro agent parameters set proxy-node true
opsbro agent parameters set node-zone  gabes-home

AGENT_FILE=/etc/opsbro/agent.yml

cat $AGENT_FILE


print_header "Checking values"

assert_in_file 'display_name: node-1'      $AGENT_FILE
assert_in_file 'SET display_name → node-1' $AGENT_FILE

assert_in_file 'node-zone: gabes-home'            $AGENT_FILE
assert_in_file 'SET node-zone → gabes-home'       $AGENT_FILE

assert_in_file 'proxy-node: true'          $AGENT_FILE
assert_in_file 'SET proxy-node → true'     $AGENT_FILE



print_header "Setting values in a pack"

ls /var/lib/opsbro
OVERLOAD_PACK=/var/lib/opsbro/local-configuration/packs/grafana
assert_directory_missing "$OVERLOAD_PACK"

opsbro  packs overload global.grafana
assert_directory_exists  "$OVERLOAD_PACK"

GRAFANA_KEY=eyJrIjoibmhIR0FuRnB0MTN6dFBMTlNMZDZKWjJXakFuR0I2Wk4iLCJuIjoiT3BzQnJvIiwiaWQiOjF9
opsbro  packs parameters set local.grafana.api_key  $GRAFANA_KEY
assert_in_file $GRAFANA_KEY $OVERLOAD_PACK/parameters/parameters.yml


GET=$(opsbro  packs parameters  get local.grafana.api_key)
echo "$GET"
echo "$GET" | grep $GRAFANA_KEY
if [ $? != 0 ];then
   echo "ERROR: should be the grafana key in the get result"
   echo "$GET"
fi


exit_if_no_crash "TEST OK"