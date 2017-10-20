#!/usr/bin/env bash

/etc/init.d/opsbro start


opsbro dashboards show linux

printf "Demo is finish, OpsBro is able of far more than just a dashboard, more to come in the documentation very soon (⌐■_■)\n"
sleep 2

python bin/opsbro banner

python bin/opsbro sponsor
