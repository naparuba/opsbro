#!/bin/bash

# FROM: https://github.com/andrew-d/static-binaries

set -e
set -o pipefail
set -x



cd /build

# Download
curl -LO http://ftp.gnu.org/gnu/termcap/termcap-${TERMCAP_VERSION}.tar.gz
tar zxvf termcap-${TERMCAP_VERSION}.tar.gz
cd termcap-${TERMCAP_VERSION}

# Build
CC="${GCC} -static -fPIC" ./configure --disable-shared --enable-static
make -j4
