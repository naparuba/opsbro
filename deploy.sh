#!/bin/bash

cd /root
tar cfz opsbro-oss.tar.gz opsbro-oss


do_deploy() {
    if [[ "X" == "X$1" ]]; then
        return
    fi
    printf "********* Server: $1 \n";
    SCP=$(scp opsbro-oss.tar.gz $1:/tmp)
    SSH1=$(ssh $1 "cd /tmp;rm -fr opsbro-oss; tar xfz /tmp/opsbro-oss.tar.gz")
    SSH2=$(ssh $1 "cd /tmp/opsbro-oss;python setup.py install" >/tmp/res-$1.txt 2>&1)
    if [ $? -ne 0 ]; then
	echo "FAIL $1 (BUILD)::"
	echo "LOOK at file /tmp/res-$1.txt"
	printf "\n\n"
	return 2
    fi;

    SCP1=$(scp -r /root/opsbro-oss/data/* $1:/var/lib/opsbro/ >/dev/null)
    # NOTE: do nto copy etc/ local.json
    #SCP2=$(scp -r /etc/opsbro/* $1:/etc/opsbro/  >/dev/null)

    SSH3=$(ssh $1 "/etc/init.d/opsbro stop; sleep 3; /etc/init.d/opsbro start" >/tmp/res-$1.txt 2>&1)
    if [ $? -ne 0 ]; then
	
	echo "FAIL $1 (RESTART)::"
	echo "LOOK at file /tmp/res-$1.txt"
	printf "\n\n"
	return 2
    fi;
    printf "Server: %-20s :: OK\n" "$1"
}
export -f do_deploy

cat servers | xargs --delimiter='\n' -n 1 -P 10 -I {} bash -c 'do_deploy "{}"'

