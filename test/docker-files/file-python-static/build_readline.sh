#!/bin/bash

# FROM: https://github.com/andrew-d/static-binaries

set -e
set -o pipefail
set -x




cd /build

# Download
curl -LO ftp://ftp.cwru.edu/pub/bash/readline-${READLINE_VERSION}.tar.gz
tar xzvf readline-${READLINE_VERSION}.tar.gz
cd readline-${READLINE_VERSION}

# Build
CC="${GCC} -static -fPIC" ./configure --disable-shared --enable-static
make -j4

# Note that things look for readline in <readline/readline.h>, so we need
# that directory to exist.
ln -s /build/readline-${READLINE_VERSION} /build/readline-${READLINE_VERSION}/readline

