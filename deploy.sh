#!/bin/bash

cd /root
tar cfz kunai-oss.tar.gz kunai-oss

/bin/cp -frp /root/kunai-oss/ui/* /var/www/ui/


do_deploy() {
    if [[ "X" == "X$1" ]]; then
        return
    fi
    printf "********* Server: $1 \n";
    SCP=$(scp kunai-oss.tar.gz $1:/tmp)
    SSH1=$(ssh $1 "cd /tmp;rm -fr kunai-oss; tar xfz /tmp/kunai-oss.tar.gz")
    SSH2=$(ssh $1 "cd /tmp/kunai-oss;python setup.py install" >/tmp/res-$1.txt 2>&1)
    if [ $? -ne 0 ]; then
	echo "FAIL $1 (BUILD)::"
	echo "LOOK at file /tmp/res-$1.txt"
	printf "\n\n"
	return 2
    fi;

    SCP1=$(scp -r /root/kunai-oss/data/* $1:/var/lib/kunai/ >/dev/null)
    # NOTE: do nto copy etc/ local.json
    #SCP2=$(scp -r /etc/kunai/* $1:/etc/kunai/  >/dev/null)

    SSH3=$(ssh $1 "/etc/init.d/kunai stop; sleep 3; /etc/init.d/kunai start" >/tmp/res-$1.txt 2>&1)
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

