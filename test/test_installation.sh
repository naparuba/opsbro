#!/usr/bin/env bash


# Travis: only need to run the installation once, it it not link to a specific python version. They don't need to use CPU for nothing ;)
if [ "X$TRAVIS_PYTHON_VERSION" == "X2.6" ]; then
   echo "Skippping installation tests for travis 2.6 configuration, only need one launch (2.7)"
   exit 0
fi

echo "Launching installations tests for SUITE: $TEST_SUITE"

cd ..





function print_color {
   export COLOR="$2"
   export TEXT="$1"
   python -c "from opsbro.log import cprint;cprint('$TEXT', color='$COLOR', end='')"
}

export -f print_color

function get_var_name {
   II=$1
   DOCKER_FILE_FULL=`basename $1`
   DOCKER_FILE=`echo "$DOCKER_FILE_FULL" | cut -d'.' -f1| tr "-" "_"`
   echo "$DOCKER_FILE"
}

export SUCCESS_FILE=/tmp/opsbro.test.installation.success
export FAIL_FILE=/tmp/opsbro.test.installation.fail

# Clean results files
> $SUCCESS_FILE
> $FAIL_FILE


function launch_docker_file {
   FULL_PATH=$1
   DO_WHAT=$2

   DOCKER_FILE=`basename $FULL_PATH`
   NOW=$(date +"%H:%M:%S")
   print_color "$DO_WHAT  $DOCKER_FILE : BUILD starting at $NOW \n" "magenta"
   LOG=/tmp/build-and-run.$DOCKER_FILE.log
   rm -fr $LOG
   BUILD=$(docker build --quiet -f $FULL_PATH .  2>&1)
   if [ $? != 0 ]; then
       echo "$BUILD" > $LOG
       FAIL="TRUE"

       # Maybe it just fail due to "Cannot overwrite digest" (concurrent build), if so, restart build
       grep "Cannot overwrite digest" $LOG > /dev/null
       if [ $? == 0 ];then
          echo "RESTART BUILD"
          > $LOG
          BUILD=$(docker build --quiet -f $FULL_PATH .  2>&1)
          if [ $? == 0 ]; then
             # OK back to OK
             FAIL="FALSE"
          fi
          echo "$BUILD" > $LOG
       fi

       if [ $FAIL == "TRUE" ];then
          print_color "$DO_WHAT  ERROR: $DOCKER_FILE" "red"
          printf " `date` Cannot build. Look at $LOG\n"
          printf "$DOCKER_FILE\n" >> $FAIL_FILE
          cat $LOG
          return
       fi
   fi

   NOW=$(date +"%H:%M:%S")
   if [ "$DO_WHAT" == "BUILD_ONLY" ];then
      print_color "OK: $DOCKER_FILE  build only phase finish at $NOW \n" "green"
      return
   fi

   SHA=`echo $BUILD|cut -d':' -f2`

   print_color "$DO_WHAT  $DOCKER_FILE : RUN starting at $NOW \n" "magenta"
   docker run --interactive -a stdout -a stderr --rm=true --privileged --cap-add ALL  "$SHA" 2>>$LOG >>$LOG
   if [ $? != 0 ]; then
       print_color "$DO_WHAT  ERROR: `date` $DOCKER_FILE" "red"
       printf "  Cannot run. Look at $LOG\n"
       printf "$DOCKER_FILE\n" >> $FAIL_FILE
       cat $LOG
       return
   fi
   NOW=$(date +"%H:%M:%S")
   print_color "$DO_WHAT  OK: $DOCKER_FILE" "green"
   printf " at $NOW (log=$LOG)\n"
   printf "$DOCKER_FILE\n" >> $SUCCESS_FILE
}


export -f launch_docker_file

NB_CPUS=`python -c "import multiprocessing;print multiprocessing.cpu_count()"`
echo "Detected number of CPUs: $NB_CPUS"
# Travis: be sure to use the 2 CPU available, and in fact to allow // connections so we keep the test time bellow the limit
#if [ "X$TRAVIS" == "Xtrue" ]; then
#   NB_CPUS=10
#   echo "Travis detected, using $NB_CPUS CPUs"
   # if stats with DUO, allow far more than this
   #if [[ $TEST_SUITE == DUO* ]] || [[ $TEST_SUITE == DEMO* ]]; then
   #   NB_CPUS=6
   #   echo "Travis detected, and also DUO test based. Allow more CPUs; $NB_CPUS"
   #fi
#fi

NB_DISTRIBUTED_LAUNCHS=1
# On TRAVIS: 5 launchs
if [ "X$TRAVIS" == "Xtrue" ]; then
   NB_DISTRIBUTED_LAUNCHS=5
fi

# For compose, we are asking to docker-compose to build and run
if [[ $TEST_SUITE == COMPOSE* ]];then

   # Compose should be run numerous time to be sure they are stable
   for ii in `seq 1 $NB_DISTRIBUTED_LAUNCHS`; do
       # In compose, we MUST be sure we are the only launched instance with no state before us
       if [ "X$TRAVIS" == "Xtrue" ]; then
          docker system prune --force >/dev/null
       fi

       COMPOSE_FILE=test/docker-files/docker-$TEST_SUITE

       NOW=$(date +"%H:%M:%S")
       print_color "[$ii] BUILD  $COMPOSE_FILE : BUILD starting at $NOW \n" "magenta"
       LOG=/tmp/build-and-run.docker-$TEST_SUITE.log
       > $LOG
       docker-compose  -f $COMPOSE_FILE build 2>>$LOG  >>$LOG
       if [ $? != 0 ]; then
           print_color "$ii BUILD ERROR: $COMPOSE_FILE" "red"
           printf " `date` Cannot build. Look at $LOG\n"
           cat $LOG
           exit 2
       fi


       NOW=$(date +"%H:%M:%S")
       print_color "[$ii] RUN  $COMPOSE_FILE : RUN starting at $NOW \n" "magenta"
       # Build was ok, we can clean the log
       > $LOG
       docker-compose  -f $COMPOSE_FILE up --build 2>>$LOG  >>$LOG
       # NOTE: compose up do not exit with worse state, so must look at the
       # docker-copose ps to have exit states
       # +3=> remvoe the first 2 line of the ps (header)
       PS_STATES=$(docker-compose  -f $COMPOSE_FILE ps | tail -n +3)
       echo "$PS_STATES" >> $LOG
       echo "[$ii] Container results:"
       echo "$PS_STATES"
       NB_BADS=$(echo "$PS_STATES" | grep -v 'Exit 0' | grep -v '^$' | wc -l)
       echo "[$ii] NB BADS containers: $NB_BADS"
       if [ $NB_BADS != 0 ]; then
           print_color "[$ii] RUN ERROR: $COMPOSE_FILE" "red"
           printf " `date` Cannot run. Look at $LOG\n"
           cat $LOG
           exit 2
       fi
       echo "OK Finish occurence $ii"
   done

   NOW=$(date +"%H:%M:%S")
   print_color "BUILD  $COMPOSE_FILE : is finish OK at $NOW \n" "green"
   exit 0
fi


# Only do the test suite we must do
DOCKER_FILES=`ls -1 test/docker-files/docker-file-$TEST_SUITE-*txt`

# export TRAVIS var so xargs calls with have it
export TRAVIS=$TRAVIS
echo "================================================= Building all images first:"
# NOTE: builds are unlimited because it's mainly network
echo $DOCKER_FILES | xargs --delimiter=' ' --no-run-if-empty -n 1 -P 99 -I {} bash -c 'launch_docker_file "{}" "BUILD_ONLY"'

# Run must be synchronizer if possible, will allow to have less issues in synchronized tests (like DUO or DEMO)
printf "\n\n\n"
echo "================================================= Then Running all images:"
echo $DOCKER_FILES | xargs --delimiter=' ' --no-run-if-empty -n 1 -P $NB_CPUS -I {} bash -c 'launch_docker_file "{}" "RUN"'


printf "Some tests are OK:\n"
cat $SUCCESS_FILE

ALL_ERRORS=$(cat $FAIL_FILE)
if [ "X$ALL_ERRORS" == "X" ]; then
   echo "OK, no errors."
   exit 0
else
   echo "ERRORS: some tests did fail:"
   cat $FAIL_FILE
   exit 1
fi
