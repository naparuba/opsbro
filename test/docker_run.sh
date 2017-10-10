#!/usr/bin/env bash

MODE="$1"
DF="$2"


if [ $MODE == "test" ]; then
   docker run --cap-add=SYS_PTRACE --tty --interactive --entrypoint=/bin/bash `docker build -q -f test/docker-files/$DF .| cut -d':' -f2`
   exit $?
fi


if [ $MODE == "run" ]; then
   docker run --cap-add=SYS_PTRACE --tty --interactive  `docker build -q -f test/docker-files/$DF .| cut -d':' -f2`
   exit $?
fi


if [ $MODE == "build" ]; then
   docker build -f test/docker-files/$DF .
   exit $?
fi


if [ $MODE == "run" ]; then
   docker run --cap-add=SYS_PTRACE --tty --interactive  `docker build -q -f test/docker-files/$DF .| cut -d':' -f2`
   exit $?
fi

