#!/usr/bin/env bash

# First clean all previous entries in the share directory

SHARE=/tmp/share

rm -f $SHARE/*

# First the installation
asciinema rec -y -w 0.3 -t "OpsBro Installation" -c "/bin/bash test/tutorial-scripts/installation.sh" $SHARE/installation.json

# Then agent start
asciinema rec -y -w 0.3 -t "OpsBro agent start" -c "/bin/bash test/tutorial-scripts/start.sh" $SHARE/start.json

# Opsbro
asciinema rec -y -w 0.3 -t "OpsBro CLI" -c "/bin/bash test/tutorial-scripts/cli.sh" $SHARE/cli.json

# Show agent info
asciinema rec -y -w 2 -t "OpsBro agent info" -c "/bin/bash test/tutorial-scripts/agent-info.sh" $SHARE/agent-info.json

# Show agent info
asciinema rec -y -w 0.3 -t "OpsBro linux dashboard" -c "/bin/bash test/tutorial-scripts/linux-dashboard.sh" $SHARE/linux-dashboard.json

echo "All tutorials are done"

echo "Uploading them"

# We need to avoid some SSL error in debian
printf "\nurl= http://asciinema.org\n" >>~/.config/asciinema/config

for ii in $(ls -1 /tmp/share/*json); do
   echo "Uploading  $ii"
   asciinema upload $ii
done

echo "All upload are OK"
