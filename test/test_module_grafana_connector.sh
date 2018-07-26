#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh



print_header "Starting to test Grafana"

# We will modify a pack, so overload it first
opsbro  packs overload global.grafana

# Change module parameters for Grafana
opsbro  packs parameters set local.grafana.api_key               'eyJrIjoibmhIR0FuRnB0MTN6dFBMTlNMZDZKWjJXakFuR0I2Wk4iLCJuIjoiT3BzQnJvIiwiaWQiOjF9'


# We can start opsbro first, as the api_key is already configured
# and we will add the group dynamically

/etc/init.d/opsbro start


# Create sqlite as the file is not created at setup
/etc/init.d/grafana-server start
sleep 5
/etc/init.d/grafana-server stop

# We need an API key, insert it
print_header "Creating the API key into th SQLITE database"
sqlite3 /var/lib/grafana/grafana.db "INSERT INTO 'api_key' VALUES(1,1,'OpsBro','6799edffb8d523e4cbbbc7cea83269576689aeffdd7a88aa775622bacf8ac0bd653a333b94a525d4394a34c9ee1f41bbab25','Admin','2017-09-15 20:00:37','2017-09-15 20:00:37');"

if [ $? != 0 ]; then
    echo "ERROR: the grafana connector test did fail, sqlite did fail"
    exit 2
fi


/etc/init.d/grafana-server start

sleep 5

print_header "Checking for authentification"
OUT=$(curl -s -H "Authorization: Bearer eyJrIjoibmhIR0FuRnB0MTN6dFBMTlNMZDZKWjJXakFuR0I2Wk4iLCJuIjoiT3BzQnJvIiwiaWQiOjF9" http://localhost:3000/api/dashboards/home)

printf "$OUT"|grep --color timepicker

if [ $? != 0 ]; then
    echo "ERROR: the grafana connector is not OK when check the auth with curl"
    printf "$OUT"
    exit 2
fi

# We can now enable the grafana module y setting the valid group
# Enable DNS module
opsbro agent parameters add groups grafana-connector
if [ $? != 0 ]; then
    echo "ERROR: the grafana connector is not OK on data source insert"
    exit 2
fi

# Wait a bit for the module to work
sleep 10

print_header "Checking if the data source is created, with NAME--opsbro--NODE_UUID as name"

curl -s -H "Authorization: Bearer eyJrIjoibmhIR0FuRnB0MTN6dFBMTlNMZDZKWjJXakFuR0I2Wk4iLCJuIjoiT3BzQnJvIiwiaWQiOjF9" http://localhost:3000/api/datasources | grep --color opsbro
if [ $? != 0 ]; then
    curl -s -H "Authorization: Bearer eyJrIjoibmhIR0FuRnB0MTN6dFBMTlNMZDZKWjJXakFuR0I2Wk4iLCJuIjoiT3BzQnJvIiwiaWQiOjF9" http://localhost:3000/api/datasources
    cat /var/log/opsbro/module.grafana.log
    echo "ERROR: the grafana connector is not OK on data source insert"
    exit 2
fi


print_header "OK:  grafana export is working"
