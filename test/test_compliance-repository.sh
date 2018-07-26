#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh


print_header "Starting to test Compliance for mongodb install with repository"


# Start daemon
/etc/init.d/opsbro start


opsbro compliance wait-compliant "MONGODB-INSTALL" --timeout=120
if [ $? != 0 ];then
   echo "ERROR: cannot have the repository compliance rule compliant."
   opsbro compliance state
   opsbro compliance history
   exit 2
fi



# We now should have the mongodb-org package installed
mongod --version |grep 'db version'
if [ $? != 0 ];then
   echo "ERROR: mongodb do not seems to be installed."
   opsbro compliance state
   opsbro compliance history
   exit 2
fi



opsbro compliance state
opsbro compliance history

print_header "Mongodb install by repository compliance rule is OK"
exit 0
