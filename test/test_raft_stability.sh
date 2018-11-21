#!/usr/bin/env bash

# Load common shell functions
MYDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $MYDIR/common_shell_functions.sh

export NB_TRY=5

IN_ERROR="False"


function launch_trys {
    IN_ERROR="False"
    total_seconds=0
    export NB_NODES_BY_CPU="$1"
    export TEST_TIMEOUT=20
    for ii in `seq 1 $NB_TRY`; do
       LOG=/tmp/try.log
       > $LOG
       # RESET BASH COUNTER
       SECONDS=0
       python test_raft.py  TestRaft.test_raft_large_leader_election >>$LOG 2>>$LOG
       if [ $? != 0 ];then
          echo "ERROR: fail after $ii try:"
          #cat /tmp/try.log
          IN_ERROR="True"
          return 2
       fi

       # do some work
       duration=$SECONDS
       total_seconds=$(echo $total_seconds + $duration | bc)
       ELAPSED="Elapsed: $duration sec"
       #echo "$(($duration / 60)) minutes and  seconds elapsed."
       printf "\r TRY: [size=${NB_NODES_BY_CPU}] -- $ii/$NB_TRY : OK ( this turn=$ELAPSED   -- total=$total_seconds)"
    done
    printf '\n'
    average_time=$(echo $total_seconds / $NB_TRY | bc)
    echo "  SUCCESS [size=${NB_NODES_BY_CPU}]  after $NB_TRY try (total seconds=${total_seconds}s  -- average time=${average_time}s )"
    IN_ERROR="False"
}

PHASE="INCREASE"

CURRENT_NODE_BY_CPU=5
LAST_VALID_NODE_BY_CPU=$CURRENT_NODE_BY_CPU
# Finding the more stable value
# Phase1:
 # Increasing: *2 values:
 # * success: try again the *2
 # * fail: go decrease
# Phase2:
 # Decrease: we /2 with our last working value
 # * success: we found our final value
 # * fail: /2 with the last working value
# Phase3:
 # slow-increase: we /2 with the last bad
 # * success: /2 again
 # * fail: STOP: the last working is our final result

for exp in `seq 1 300`; do
    if [ $PHASE == "INCREASE" ];then
        CURRENT_NODE_BY_CPU=$(echo "$CURRENT_NODE_BY_CPU * 2" |bc)
        launch_trys "$CURRENT_NODE_BY_CPU"
        if [ "$IN_ERROR" == "True" ];then
           PHASE="DECREASE"
           echo "Test did fail at $CURRENT_NODE_BY_CPU => go DECREASE"
           LAST_BAD_NODE_BY_CPU=$CURRENT_NODE_BY_CPU
           continue
        fi
        LAST_VALID_NODE_BY_CPU=$CURRENT_NODE_BY_CPU
        continue  # go *2
    fi
    if [ $PHASE == "DECREASE" ];then
        PREVIOUS_NODE_BU_CPU=$CURRENT_NODE_BY_CPU
        CURRENT_NODE_BY_CPU=$(echo "($LAST_VALID_NODE_BY_CPU + (($CURRENT_NODE_BY_CPU - $LAST_VALID_NODE_BY_CPU ) / 2) )/1" |bc)  # bc=> /1 make float=>int

        # If we are stable, quit
        TEST_DIFF=$(echo "$CURRENT_NODE_BY_CPU - $PREVIOUS_NODE_BU_CPU" |bc)
        TEST_DIFF=${TEST_DIFF/-/}  # absolute
        if [ $TEST_DIFF -le 1 ];then
            echo "TEST is enought stable, exiting"
            echo "FINAL VALUE did found: $LAST_VALID_NODE_BY_CPU."
            exit 0
        fi

        echo " * Decreasing ( last working is $LAST_VALID_NODE_BY_CPU current $CURRENT_NODE_BY_CPU)"
        launch_trys "$CURRENT_NODE_BY_CPU"
        if [ "$IN_ERROR" == "True" ];then
            LAST_BAD_NODE_BY_CPU=$CURRENT_NODE_BY_CPU
            continue
        fi
        echo "Decreasing phase did STOP. Go slow increasing: $CURRENT_NODE_BY_CPU"
        PHASE='SLOW-INCREASE'
        LAST_VALID_NODE_BY_CPU=$CURRENT_NODE_BY_CPU

        continue
    fi
    if [ $PHASE == "SLOW-INCREASE" ];then
        #CURRENT_NODE_BY_CPU=$(echo "$LAST_VALID_NODE_BY_CPU + 1" |bc)
        PREVIOUS_NODE_BU_CPU=$CURRENT_NODE_BY_CPU
        CURRENT_NODE_BY_CPU=$(echo "($CURRENT_NODE_BY_CPU + (($LAST_BAD_NODE_BY_CPU - $CURRENT_NODE_BY_CPU ) / 2) )/1" |bc)  # bc=> /1 make float=>int

        TEST_DIFF=$(echo "$CURRENT_NODE_BY_CPU - $PREVIOUS_NODE_BU_CPU" |bc)
        TEST_DIFF=${TEST_DIFF/-/}  # absolute
        if [ $TEST_DIFF -le 1 ];then
            echo "TEST is enought stable, exiting"
            echo "FINAL VALUE did found: $LAST_VALID_NODE_BY_CPU."
            exit 0
        fi

        echo " * Slow increase ( last working is $LAST_VALID_NODE_BY_CPU, last bad is $LAST_BAD_NODE_BY_CPU, current $CURRENT_NODE_BY_CPU)"
        launch_trys "$CURRENT_NODE_BY_CPU"
        if [ "$IN_ERROR" == "True" ];then
           #echo "FINAL VALUE did found: $LAST_VALID_NODE_BY_CPU."
           #exit 0
           PHASE="DECREASE"
           echo "Test did fail at $CURRENT_NODE_BY_CPU => go DECREASE"
           LAST_BAD_NODE_BY_CPU=$CURRENT_NODE_BY_CPU
           continue
        fi
        LAST_VALID_NODE_BY_CPU=$CURRENT_NODE_BY_CPU
        continue  # go cut by half with last bad node
    fi
done

Echo "Magic $CURRENT_NODE_BY_CPU"