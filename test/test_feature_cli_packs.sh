#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test CLI packs commands"

### List is here to show all packs
opsbro packs list
if [ $? != 0 ]; then
   echo "ERROR: the packs list did fail."
   exit 2
fi

# There should be none overloaded packs,
# also test for overload filter
opsbro packs list --only-overloads | grep 'No packs matchs the request'
if [ $? != 0 ]; then
   echo "ERROR: There should not be any overload packs by default."
   exit 2
fi

print_header "Overloading the stats pack"
# We should allow to overload a global pack to a local one
opsbro packs overload global.statsd
if [ $? != 0 ]; then
   echo "ERROR: overload command did fail."
   exit 2
fi

# Now the statsd pack should be overload
opsbro packs list --only-overloads | grep 'statsd'
if [ $? != 0 ]; then
   echo "ERROR: The statsd module should be overload."
   exit 2
fi

# There should be the pack directory exiting
if [ ! -d '/var/lib/opsbro/local-configuration/packs/statsd' ]; then
   echo "ERROR: the pack directory is missing"
   exit 2
fi

# core packs are NOT allowed to be overloaded
opsbro packs overload core.core-cli-agent
if [ $? == 0 ]; then
   echo "ERROR: We do not authorize to overload core packs."
   exit 2
fi

print_header "Look at local statsd parameters setting/overload"
# get a missing property should fail
opsbro packs parameters get local.statsd.missing
if [ $? == 0 ]; then
   echo "ERROR: the get command should have failed"
   exit 2
fi

# get a missing property should fail
opsbro packs parameters get local.statsd.port
if [ $? != 0 ]; then
   echo "ERROR: the get command should have failed"
   exit 2
fi

# but an existing one should be ok
opsbro packs parameters get local.statsd.port
if [ $? != 0 ]; then
   echo "ERROR: the get command should have failed"
   exit 2
fi

# With a good value
opsbro packs parameters get local.statsd.port | grep 8125
if [ $? != 0 ]; then
   echo "ERROR: the value should have been 8125"
   exit 2
fi

print_header "Try to setting stats parameters"

# Try to configure a parameter, but with a wrong type for MODULE
opsbro packs parameters set local.statsd.port "just a string"
if [ $? == 0 ]; then
   echo "ERROR: Only a int value should be authorized here"
   exit 2
fi

# Try to configure a parameter, but with a wrong type for COLLECTOR
opsbro packs parameters set global.mongodb.replicat_set "just a string"
if [ $? == 0 ]; then
   echo "ERROR: Only a bool value should be authorized here"
   exit 2
fi

# Try to configure a parameter, but with a wrong name
opsbro packs parameters set local.statsd.wrong_name "just a string"
if [ $? == 0 ]; then
   echo "ERROR: Only a int value should be authorized here"
   exit 2
fi

# Try to configure a parameter, but with a wrong type
opsbro packs parameters set local.statsd.port 8126
if [ $? != 0 ]; then
   echo "ERROR: cannot set the port value"
   exit 2
fi

# get a missing property should fail
opsbro packs parameters get local.statsd.port | grep 8126
if [ $? != 0 ]; then
   echo "ERROR: the value should have been 8126"
   exit 2
fi

exit_if_no_crash "OK:  cli packs is working well"
