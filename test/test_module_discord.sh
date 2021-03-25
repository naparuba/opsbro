#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

print_header "Starting to test Discord module"

# Set a valid display name for debug
opsbro agent parameters set display_name "node-discord"

opsbro packs overload global.discord

if [ "X$DISCORD_TOKEN" == "X" ] || [ "X$DISCORD_CHANNEL" == "X" ]; then
   do_bad_exit_and_logs "ERROR: DISCORD_TOKEN or DISCORD_CHANNEL env variable for this test"
fi

echo "Using channel : $DISCORD_CHANNEL"

# Change module parameters for Grafana
opsbro packs parameters set local.discord.token "$DISCORD_TOKEN"
opsbro packs parameters set local.discord.channel_id "$DISCORD_CHANNEL"

# Enable Discord module
opsbro agent parameters add groups discord

# Start it
/etc/init.d/opsbro --debug start
assert_no_crash

print_header "Wait for discord prereqs"
opsbro compliance wait-compliant "Install python3-aiohttp if discord module enabled" --timeout=60
if [ $? != 0 ]; then
   echo ""
   opsbro compliance state
   opsbro compliance history
   cat /var/log/opsbro/compliance.log
   cat /var/log/opsbro/crash.log 2>/dev/null
   do_bad_exit_and_logs "ERROR: the local discord prereqs cannot be installed"
fi

# Centos: don't know why, but the aiohttp lib cannot be load unless restart
/etc/init.d/opsbro --debug restart
assert_no_crash

print_header "Checking module is working"
opsbro agent info

ls -thor /var/log/opsbro/

sleep 30

cat /var/log/opsbro/module.discord.log

# Currently: no crash? it's ok ^^

opsbro agent modules state

exit_if_no_crash "opsbro Discord module is OK"
