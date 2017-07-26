#!/usr/bin/env bash

cd ..

DOCKER_FILES=`ls -1 test/docker-files/docker-file-*txt`


function print_color {
   export COLOR="$2"
   export TEXT="$1"
   python -c "from kunai.log import cprint;cprint('$TEXT', color='$COLOR', end='')"
}

export -f print_color

function get_var_name {
   II=$1
   DOCKER_FILE_FULL=`basename $1`
   DOCKER_FILE=`echo "$DOCKER_FILE_FULL" | cut -d'.' -f1| tr "-" "_"`
   echo "$DOCKER_FILE"
}

export SUCCESS_FILE=/tmp/kunai.test.installation.success
export FAIL_FILE=/tmp/kunai.test.installation.fail

# Clean results files
> $SUCCESS_FILE
> $FAIL_FILE


function try_installation {
   FULL_PATH=$1
   DOCKER_FILE=`basename $FULL_PATH`
   print_color "$DOCKER_FILE : starting \n" "magenta"
   LOG=/tmp/build-and-run.$DOCKER_FILE.log
   rm -fr $LOG
   BUILD=$(docker build --quiet -f $FULL_PATH .  2>&1)
   if [ $? != 0 ]; then
       print_color "ERROR:$DOCKER_FILE" "red"
       printf "Cannot build. Look at $LOG\n"
       printf "$DOCKER_FILE\n" >> $FAIL_FILE
       return
   fi

   SHA=`echo $BUILD|cut -d':' -f2`

   docker run --interactive -a stdout -a stderr --rm=true  "$SHA" 2>&1 >$LOG
   if [ $? != 0 ]; then
       print_color "ERROR: $DOCKER_FILE" "red"
       printf "  Cannot run. Look at $LOG\n"
       printf "$DOCKER_FILE\n" >> $FAIL_FILE
       # Note: under travis we cannot look at the log AFTER so we must print it now
       if [ "X$TRAVIS" == "Xtrue" ]; then
          cat $LOG
       fi
       return
   fi
   print_color "OK: $DOCKER_FILE" "green"
   printf "  (log=$LOG)\n"
   printf "$DOCKER_FILE\n" >> $SUCCESS_FILE
}


export -f try_installation

echo $DOCKER_FILES | xargs --delimiter=' ' --no-run-if-empty -n 1 -P 2 -I {} bash -c 'try_installation "{}"'

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
