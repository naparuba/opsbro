import os
import leveldb
import time
import threading
import random
import shutil
import socket
import base64
import cPickle
import marshal
import json
import hashlib
SERIALIZER = cPickle


# DO NOT FORGEET:
# sysctl -w net.core.rmem_max=26214400

from kunai.stats import STATS
from kunai.log import logger
from kunai.threadmgr import threader
from kunai.now import NOW
from kunai.util import to_best_int_float


# Will have to forward to graphit intead
class UDPSender(object):
   def __init__(self, clust):
      self.clust = clust
      
      
   def push_key(self, k, v, ttl=0):
      T0 = time.time()
      STATS.incr('ts.graphite.push-key', 1)
      v64 = base64.b64encode(v)
      logger.debug("PUSH KEY", k, "and value", len(v64))
      #self.clust.put_key(k, v64, allow_udp=True, ttl=ttl)
      self.clust.stack_put_key(k, v64, ttl=ttl)
      STATS.timer('ts.graphite.push-key', (time.time() - T0)*1000)
      return




class TSBackend(object):
   def __init__(self, usender, clust):
      #self.its = its
      self.usender = usender
      self.data = {}
      self.data_lock = threading.RLock()
      self.max_data_age = 5
      # Get a db with all our metrics listed
      # We will save all the metrics we have
      self.clust = clust
      self.db_dir = os.path.join(clust.data_dir, 'ts')
      self.db = leveldb.LevelDB(self.db_dir)
      # Ok start our inner thread
      self.launch_reaper_thread()


   # push a name but return if the name was already there or not
   def set_name_if_unset(self, key):
      try:
         self.db.Get(key, fill_cache=False)
      except KeyError:
         self.db.Put(key, '')
         logger.debug('TS propagating a new key', key)
         # now propagate the key to the other ts nodes
         self.clust.stack_new_ts_broadcast(key)
      return False


   # List all keys in our name db that match the begining of key
   def list_keys(self, key):
      if key:
         start = key
         l = chr(ord(key[-1]) + 1)
         end = key[:-1]+l
         print "LOOKUP from %s to %s" % (start, end)
         r = self.db.RangeIter(start, end, include_value=False, fill_cache=False)
      else: # Full scan? are you crazy?
         print "LOOKUP full scan"
         r = self.db.RangeIter(include_value=False, fill_cache=False)         
      return list(r)
      
      


   # We consume data and create a new data entry if need
   def add_value(self, t, key, v):
      # do nothing, will have to forward to graphite instead
      return

   # The reaper thread look at old minute objects that are not updated since long, and 
   # force to archive them
   def launch_reaper_thread(self):
       threader.create_and_launch(self.do_reaper_thread, name='TS-reaper-thread')
       

   def do_reaper_thread(self):
       while True:
          time.sleep(1) # no more need as we will forward ts
                   




class TSListener(object):
   def __init__(self, clust):
      self.clust = clust
      self.addr = '0.0.0.0'
      self.statsd_port = 8125
      self.graphite_port = 2003
      self.last_write = time.time()
      self.nb_data = 0
      self.stats_interval = 10

      # Do not step on your own foot...
      self.stats_lock = threading.RLock()
      
      # our main data structs
      self.gauges = {}
      self.timers = {}
      self.histograms = {}
      self.counters = {}
      
      # our helper objects
      #self.its = IdxTSDatabase(self.clust)
      self.usender = UDPSender(self.clust)
      self.tsb = TSBackend(self.usender, self.clust)
      
      # Now start our threads
      # STATSD
      threader.create_and_launch(self.launch_statsd_udp_listener, name='TSL_statsd_thread')
      threader.create_and_launch(self.launch_compute_stats_thread, name='TSC_thread')
      # GRAPHITE
      threader.create_and_launch(self.launch_graphite_udp_listener, name='TSL_graphite_udp_thread')
      threader.create_and_launch(self.launch_graphite_tcp_listener, name='TSL_graphite_tcp_thread')
      self.graphite_queue = []
      threader.create_and_launch(self.graphite_reaper, name='graphite-reaper-thread')
      

   def log(self, *args):
      logger.log(*args)
      

   # push a name but return if the name was already there or not
   def set_name_if_unset(self, key):
      return self.tsb.set_name_if_unset(key)


   # list all keys that start with key
   def list_keys(self, key):
      return self.tsb.list_keys(key)
   


   # The compute stats thread compute the STATSD values each X
   # seconds and push them into the classic TS part
   def launch_compute_stats_thread(self):
      while True:
         now = time.time()
         if now > self.last_write + self.stats_interval:
            self.compute_stats()
            self.last_write = now
         time.sleep(0.1)


   def compute_stats(self):
      now = int(time.time())
      logger.debug("Computing stats")
      names = []
      
      # First gauges, we take the data and put a void dict instead so the other thread can work now
      with self.stats_lock:
         gauges = self.gauges
         self.gauges = {}

      for mname in gauges:
         _sum, nb, _min, _max = gauges[mname]
         _avg = _sum / float(nb)
         key = 'stats.gauges.'+mname
         self.tsb.add_value(now, key, _avg)
         key = 'stats.gauges.'+mname+'.min'
         self.tsb.add_value(now, key, _min)
         key = 'stats.gauges.'+mname+'.max'
         self.tsb.add_value(now, key, _max)

      # Now counters
      with self.stats_lock:
         counters = self.counters
         self.counters = {}

      for mname in counters:
         cvalue, ccount = counters[mname]
         # count
         key = 'stats.gauges.'+mname+'.count'
         self.tsb.add_value(now, key, cvalue)
         # rate
         key = 'stats.gauges.'+mname+'.rate'
         self.tsb.add_value(now, key, cvalue / self.stats_interval)

      # Now timers, lot of funs :)
      with self.stats_lock:
         timers = self.timers
         self.timers = {}

      _t = time.time()
      for (mname, timer) in timers.iteritems():
         # We will need to compute the mean_99, count_99, upper_99, sum_99, sum_quares_99
         # but also std, upper, lower, count, count_ps, sum, sum_square, mean, median
         _t = time.time()
         npvalues = np.array(timer)
         # Mean
         mean = np.mean(npvalues)
         key = 'stats.timers.'+mname+'.mean'
         self.tsb.add_value(now, key, mean)
         
         # Upper 99th, percentile
         upper_99 = np.percentile(npvalues, 99)
         key = 'stats.timers.'+mname+'.upper_99'
         self.tsb.add_value(now, key, upper_99)
         
         # Sum 99
         sum_99 = npvalues[:(npvalues<upper_99).argmin()].sum()
         key = 'stats.timers.'+mname+'.sum_99'
         self.tsb.add_value(now, key, sum_99)

         # Standard deviation
         std = np.std(npvalues)
         key = 'stats.timers.'+mname+'.std'
         self.tsb.add_value(now, key, std)

         # Simple count
         count = len(timer)
         key = 'stats.timers.'+mname+'.count'
         self.tsb.add_value(now, key, count)
         
         # Sum of all
         _sum = np.sum(npvalues)
         key = 'stats.timers.'+mname+'.sum'
         self.tsb.add_value(now, key, _sum)

         # Median of all
         median = np.percentile(npvalues, 50)
         key = 'stats.timers.'+mname+'.median'
         self.tsb.add_value(now, key, median)

         # Upper of all
         upper = np.max(npvalues)
         key = 'stats.timers.'+mname+'.upper'
         self.tsb.add_value(now, key, upper)

         # Lower of all
         lower = np.min(npvalues)
         key = 'stats.timers.'+mname+'.lower'
         self.tsb.add_value(now, key, lower)
         

   # This is ht main STATSD UDP listener thread. Should not block and 
   # be as fast as possible
   def launch_statsd_udp_listener(self):
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.log(self.udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
        self.udp_sock.bind((self.addr, self.statsd_port))
        self.log("TS UDP port open", self.statsd_port)
        self.log("UDP RCVBUF", self.udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
        while True:#not self.interrupted:
            try:
               data, addr = self.udp_sock.recvfrom(65535) # buffer size is 1024 bytes
            except socket.timeout: # loop until we got something
               continue
            
            self.log("UDP: received message:", data, addr)
            # No data? bail out :)
            if len(data) == 0:
                continue
            self.log("GETDATA", data)
            
            for line in data.splitlines():
               # avoid invalid lines
               if not '|' in line:
                  continue
               elts = line.split('|', 1)
               # invalid, no type in the right part
               if len(elts) == 1:
                  continue

               _name_value = elts[0].strip()
               # maybe it's an invalid name...
               if not ':' in _name_value:
                  continue
               _nvs = _name_value.split(':')
               if len(_nvs) != 2:
                  continue
               mname = _nvs[0].strip()
               
               # Two cases: it's for me or not
               hkey = hashlib.sha1(mname).hexdigest()
               ts_node_manager = self.clust.find_ts_node(hkey)
               # if it's me that manage this key, I add it in my backend
               if ts_node_manager != self.clust.uuid:
                  node = self.clust.nodes.get(ts_node_manager, None)
                  # threads are dangerous things...
                  if node is None:
                     continue
                  
                  # TODO: do bulk send of this, like for graphite
                  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)              
                  # do NOT use the node['port'], it's the internal communication, not the graphite one!
                  sock.sendto(line, (node['addr'], self.statsd_port))
                  sock.close()
                  continue

               # Here we are sure it's really for us, so manage it :)
               value = to_best_int_float(_nvs[1].strip())
               if not mname or value is None:
                  continue

               # Look at the type of the data
               _type = elts[1].strip()
               if len(_type) == 0:
                  continue
               
               ## Gauge: <metric name>:<value>|g
               elif _type == 'g':
                  self.nb_data += 1
                  self.log('GAUGE', mname, value)
                  with self.stats_lock:
                     gentry = self.gauges.get(mname, None)
                     if gentry is None:
                        # sum, nb, min, max
                        gentry = (0.0, 0, None, None)
                     _sum, nb, _min, _max = gentry
                     _sum += value
                     nb += 1
                     if _min is None or value < _min:
                        _min = value
                     if _max is None or value > _max:
                        _max = value
                     self.gauges[mname] = (_sum, nb, _min, _max)
                     self.log('NEW GAUGE', mname, self.gauges[mname])
                     
               ## Timers: <metric name>:<value>|ms
               ## But also 
               ## Histograms: <metric name>:<value>|h
               elif _type == 'ms' or _type == 'h':
                  self.log('timers', mname, value)
                  # TODO: avoit the SET each time
                  timer = self.timers.get(mname, [])
                  timer.append(value)
                  self.timers[mname] = timer
               ## Counters: <metric name>:<value>|c[|@<sample rate>]
               elif _type == 'c':
                  self.nb_data += 1
                  self.log('COUNTER', mname, value, "rate", 1)
                  with self.stats_lock:
                     cvalue, ccount  = self.counters.get(mname, (0,0))
                     self.counters[mname] = (cvalue + value, ccount + 1)
                     self.log('NEW COUNTER', mname, self.counters[mname])                  
               ## Meters: <metric name>:<value>|m
               elif _type == 'm':
                  self.log('METERs', mname, value)
               else: # unknow type, maybe a c[|@<sample rate>]
                  if _type[0] == 'c':
                     self.nb_data += 1
                     if not '|' in _type:
                        continue
                     srate = _type.split('|')[1].strip()
                     if len(srate) == 0 or srate[0] != '@':
                        continue
                     try:
                        rate = float(srate[1:])
                     except ValueError:
                        continue
                     # Invalid rate, 0.0 is invalid too ;)
                     if rate <= 0.0 or rate > 1.0:
                        continue
                     self.log('COUNTER', mname, value, "rate", rate)
                     with self.stats_lock:
                        cvalue, ccount = self.counters.get(mname, (0,0))
                        self.log('INCR counter', (value/rate))
                        self.counters[mname] = (cvalue + (value/rate), ccount + 1/rate)
                        self.log('NEW COUNTER', mname, self.counters[mname])
                     
   
   # Thread for listening to the graphite port in UDP (2003)
   def launch_graphite_udp_listener(self):
      self.graphite_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
      self.graphite_udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      self.graphite_udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
      self.log(self.graphite_udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
      self.graphite_udp_sock.bind((self.addr, self.graphite_port))
      self.log("TS Graphite UDP port open", self.graphite_port)
      self.log("UDP RCVBUF", self.graphite_udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
      while True:#not self.interrupted:
         try:
            data, addr = self.graphite_udp_sock.recvfrom(65535)
         except socket.timeout: # loop until we got some data
            continue
         self.log("UDP Graphite: received message:", len(data), addr)
         STATS.incr('ts.graphite.udp.receive', 1)
         self.graphite_queue.append(data)


   # Same but for the TCP connections
   # TODO: use a real daemon part for this, this is not ok for fast receive
   def launch_graphite_tcp_listener(self):
      self.graphite_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.graphite_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      self.graphite_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
      self.graphite_tcp_sock.bind((self.addr, self.graphite_port))
      self.graphite_tcp_sock.listen(5)
      self.log("TS Graphite TCP port open", self.graphite_port)
      while True:
         try:
            conn, addr = self.graphite_tcp_sock.accept()
         except socket.timeout: # loop until we got some connect
            continue
         conn.settimeout(5.0)
         logger.debug('TCP Graphite Connection address:', addr)
         data = ''
         while 1:
            try:
               ldata = conn.recv(1024)
            except Exception, exp:
               print "TIMEOUT", exp
               break
            if not ldata:
               break
            # Look at only full lines, and not the last part
            # So we look at the position of the last \n
            lst_nidx = ldata.rfind('\n')
            # take all finished lines
            data += ldata[:lst_nidx+1]
            STATS.incr('ts.graphite.tcp.receive', 1)
            self.graphite_queue.append(data)
            # stack the data with the garbage so we will continue it
            # on the next turn
            data = ldata[lst_nidx+1:]
         conn.close()
         # Also stack what the last send
         self.graphite_queue.append(data)


   # Main graphite reaper thread, that will get data from both tcp and udp flow
   # and dispatch it to the others daemons if need
   def graphite_reaper(self):
      while True:
         graphite_queue = self.graphite_queue
         self.graphite_queue = []
         if len(graphite_queue) > 0:
            logger.info("Graphite queue", len(graphite_queue))
         for data in graphite_queue:
            T0 = time.time()
            self.grok_graphite_data(data)
            STATS.timer('ts.graphite.grok-graphite-data', (time.time() - T0)*1000)
         time.sleep(0.1)
   
      
   # Lookup at the graphite lines compat,  run in the graphite-reaper thread
   def grok_graphite_data(self, data):
      STATS.incr('ts.graphite.grok.data', 1)
      forwards = {}
      for line in data.splitlines():
         elts = line.split(' ')
         elts = [s.strip() for s in elts if s.strip()]

         if len(elts) != 3:
            return
         mname, value, timestamp = elts[0], elts[1], elts[2]
         hkey = hashlib.sha1(mname).hexdigest()
         ts_node_manager = self.clust.find_ts_node(hkey)
         # if it's me that manage this key, I add it in my backend
         if ts_node_manager == self.clust.uuid:
             logger.debug("I am the TS node manager")
             try:
                 timestamp = int(timestamp)
             except ValueError:
                 return
             value = to_best_int_float(value)
             if value is None:
                 continue
             self.tsb.add_value(timestamp, mname, value)
         # not me? stack a forwarder
         else:
             logger.debug("The node manager for this Ts is ", ts_node_manager)
             l = forwards.get(ts_node_manager, [])
             l.append(line)
             forwards[ts_node_manager] = l

      for (uuid, lst) in forwards.iteritems():
          node = self.clust.nodes.get(uuid, None)
          # maybe the node disapear? bail out, we are not lucky
          if node is None:
              continue
          packets = []
          # first compute the packets
          buf = ''
          for line in lst:
              buf += line+'\n'
              if len(buf) > 1024:
                  packets.append(buf)
                  buf = ''
          if buf != '':
              packets.append(buf)

          # UDP
          sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
          for packet in packets:
             # do NOT use the node['port'], it's the internal communication, not the graphite one!
             sock.sendto(packet, (node['addr'], self.graphite_port))
          sock.close()

          '''
          # TCP mode
          sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          sock.connect( (node['addr'], self.graphite_port) )          
          for packet in packets:
             sock.sendall(packet)
          sock.close()
          '''
