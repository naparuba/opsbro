#!/bin/bash

# FROM: https://github.com/andrew-d/static-binaries

set -e
set -o pipefail
set -x



cd /build

# Download
curl -LO ftp://sourceware.org/pub/libffi/libffi-3.2.1.tar.gz
tar zxvf libffi-${LIBFFI_VERSION}.tar.gz
cd libffi-${LIBFFI_VERSION}

# Build
CC="${GCC} -static -fPIC" ./configure --disable-shared --enable-static
make -j4
