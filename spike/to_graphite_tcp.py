#!/bin/env python

import socket
import time

ADDR = 'localhost'
PORT = 2003

line = 'dc1.myblabla.bibi 33 %d\n' % time.time()

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect( (ADDR, PORT))
r = sock.sendall(line)
sock.close()

print "res", r
