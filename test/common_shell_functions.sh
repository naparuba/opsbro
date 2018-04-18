echo "Loading the common shell functions"


function show_my_system_ip {
    ip addr show | grep 'scope global' | awk '{print $2}'
}



# Count the number of members in a STATE and check if they are NB==$2
function assert_state_count {
   STATS="$3"
   i=0
   until [ $i -ge 20 ]
   do
      STATS=$(opsbro gossip members)
      NB=$(echo "$STATS" | grep 'docker-container' | grep "$1" | wc -l)
      if [ "$NB" == "$2" ]; then
          echo "OK: founded $NB $1 states nodes"
          return 0
      fi
      echo "OUPS: there should be $2 $1 but there are $NB after $i/20 try"
      i=$[$i+1]
      sleep 1
   done

   # Out and still not OK? we did fail
   echo "ERROR: there should be $2 $1 but there are $NB after 20 try"
   echo "$STATS"
   exit 2
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