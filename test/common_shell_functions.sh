echo "Loading the common shell functions"


function show_my_system_ip {
    ip addr show | grep 'scope global' | awk '{print $2}'
}



# Count the number of members in a STATE and check if they are NB==$2
function assert_state_count {
   NB=$(opsbro gossip members | grep 'docker-container' | grep "$1" | wc -l)
   if [ "$NB" != "$2" ]; then
      echo "ERROR: there should be $2 $1 but there are $NB"
      opsbro gossip members
      exit 2
   fi
   echo "OK: founded $NB $1 states nodes"
}


function wait_member_display_name_with_timeout {
    opsbro gossip wait-members --display-name "$1" --timeout $2
    if [ $? != 0 ]; then
       echo "ERROR: the node with the display name $1 is not present after $2s"
       opsbro gossip members --detail
       exit 2
    fi
}


function wait_event_with_timeout {
    opsbro gossip events wait $1 --timeout=$2
    if [ $? != 0 ]; then
         cat /var/log/opsbro/daemon.log
         cat /var/log/opsbro/gossip.log
         echo "ERROR: I do not have the event $1 after $2 seconds"
         exit 2
    fi
}