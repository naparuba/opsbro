import os
import sys
import shutil
import glob

# for ip addr
import socket
import fcntl
import struct


def make_dir(path):
   if not os.path.isdir(path):
      os.mkdir(path)



def copy_dir(source_item, destination_item):
   if os.path.isdir(source_item):
      make_dir(destination_item)
      sub_items = glob.glob(source_item + '/*')
      for sub_item in sub_items:
         copy_dir(sub_item, destination_item + '/' + sub_item.split('/')[-1])
   else:
       shutil.copy(source_item, destination_item)



def to_best_int_float(val):
   try:
      i = int(float(val))
      f = float(val)
   except ValueError:
      return None
   # If the f is a .0 value,
      # best match is int
   if i == f:
      return i
   return f


# get a dict but with key as lower
def lower_dict(d):
   r = {}
   for (k,v) in d.iteritems():
      r[k.lower()] = v
   return r



# Only works in linux
def get_public_address():
   # If I am in the DNS or in my /etc/hosts, I win
   try:
      addr = socket.gethostbyname(socket.gethostname())
      if addr != '127.0.0.1':
         return addr
   except Exception, exp:
      pass
   
   if sys.platform == 'linux2':
      for prefi in ['bond', 'eth']:
         for i in xrange(0, 10):
            ifname = '%s%d' % (prefi, i)
            try:
               addr = get_ip_address(ifname)
               return addr
            except IOError: # no such interface
               pass
   return None


# Get the ip address in a linux system
def get_ip_address(ifname):
   s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   return socket.inet_ntoa(fcntl.ioctl(
      s.fileno(),
      0x8915,  # SIOCGIFADDR
      struct.pack('256s', ifname[:15])
   )[20:24])
        
