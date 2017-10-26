#!/bin/bash

# FROM: https://github.com/andrew-d/static-binaries

set -e
set -o pipefail
set -x



cd /build

# Download
curl -LO https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz
tar zxvf openssl-${OPENSSL_VERSION}.tar.gz
cd openssl-${OPENSSL_VERSION}

# Configure
CC="${GCC} -static" ./Configure no-shared linux-x86_64

# Build
make
echo "** Finished building OpenSSL"

