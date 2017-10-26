#!/bin/bash

# FROM: https://github.com/andrew-d/static-binaries

set -e
set -o pipefail
set -x



cd /build

# Download
curl -LO http://zlib.net/zlib-${ZLIB_VERSION}.tar.gz
tar zxvf zlib-${ZLIB_VERSION}.tar.gz
cd zlib-${ZLIB_VERSION}

# Build
CC="${GCC} -static -fPIC" ./configure --static
make -j4

