#!/bin/bash

# FROM: https://github.com/andrew-d/static-binaries

set -e
set -o pipefail
set -x

OUTPUT=/build/output
mkdir $OUTPUT


cd /build

# Download
curl -LO https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz
unxz Python-${PYTHON_VERSION}.tar.xz
tar -xvf Python-${PYTHON_VERSION}.tar
cd Python-${PYTHON_VERSION}

# Set up modules
cp Modules/Setup.dist Modules/Setup
MODULES="_bisect _collections _csv _datetime _elementtree _functools _heapq _io _md5 _posixsubprocese _random _sha _sha256 _sha512 _socket _struct _weakref array binascii cmath cStringIO cPickle datetime fcntl future_builtins grp itertools math mmap operator parser readline resource select spwd strop syslog termios time unicodedata zlib"
for mod in $MODULES; do
    sed -i -e "s/^#${mod}/${mod}/" Modules/Setup
done

echo '_json _json.c' >> Modules/Setup
echo '_multiprocessing _multiprocessing/multiprocessing.c _multiprocessing/semaphore.c _multiprocessing/socket_connection.c' >> Modules/Setup

#printf "_ctypes _ctypes/_ctypes.c _ctypes/callbacks.c _ctypes/callproc.c _ctypes/cfield.c _ctypes/malloc_closure.c _ctypes/stgdict.c -lffi  -I/build/ffi -L/build/ffi \n" >> Modules/Setup

# Enable static linking
sed -i '1i\
*static*' Modules/Setup

# Set dependency paths for zlib, readline, etc.
sed -i \
    -e "s|^zlib zlibmodule.c|zlib zlibmodule.c -I/build/zlib-${ZLIB_VERSION} -L/build/zlib-${ZLIB_VERSION} -lz|" \
    -e "s|^readline readline.c|readline readline.c -I/build/readline-${READLINE_VERSION} -L/build/readline-${READLINE_VERSION} -L/build/termcap-${TERMCAP_VERSION} -lreadline -ltermcap|" \
    Modules/Setup

# Enable OpenSSL support
patch --ignore-whitespace -p1 < /build/cpython-enable-openssl.patch
sed -i -e "s|^SSL=/build/openssl-TKTK|SSL=/build/openssl-${OPENSSL_VERSION}|"  Modules/Setup

# Configure
CC="${GCC} -static -fPIC" CXX="${G_PLUS_PLUS} -static -static-libstdc++ -fPIC" LD=/opt/cross/x86_64-linux-musl/bin/x86_64-linux-musl-ld  ./configure  --disable-shared

# Build
make -j4
/opt/cross/x86_64-linux-musl/bin/x86_64-linux-musl-strip python

cp -p python $OUTPUT

# Copy the Lib into a Python.zip so we can have it when launching our build
cd Lib
zip -r $OUTPUT/python.zip *

#cp -rp $OUTPUT/* /tmp/share

echo "** Finished **"

