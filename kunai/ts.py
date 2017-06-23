import os
import time
import threading
import socket
import base64
import cPickle
import hashlib
import json

try:
    import numpy as np
except ImportError:
    np = None

from kunai.stats import STATS
from kunai.log import logger
from kunai.threadmgr import threader
from kunai.util import to_best_int_float
from kunai.now import NOW
from kunai.dbwrapper import dbwrapper
from kunai.gossip import gossiper
from kunai.stop import stopper
from kunai.kv import kvmgr
from kunai.httpdaemon import route, response

# DO NOT FORGEET:
# sysctl -w net.core.rmem_max=26214400

SERIALIZER = cPickle


class TSBackend(object):
    def __init__(self):
        self.data = {}
        self.data_lock = threading.RLock()
        self.max_data_age = 5
    
    
    # When we load, really open our database
    def load(self, data_dir):
        # Get a db with all our metrics listed
        # We will save all the metrics we have
        self.db_dir = os.path.join(data_dir, 'ts')
        self.db = dbwrapper.get_db(self.db_dir)
        # Ok start our inner thread
        self.launch_reaper_thread()
    
    
    def push_key(self, k, v, ttl=0):
        T0 = time.time()
        STATS.incr('ts.graphite.push-key', 1)
        v64 = base64.b64encode(v)
        logger.debug("PUSH KEY", k, "and value", len(v64), part='ts')
        # TODO: set allow_udp=True or not?
        kvmgr.stack_put_key(k, v64, ttl=ttl)
        STATS.timer('ts.graphite.push-key', (time.time() - T0) * 1000)
        return
    
    
    # push a name but return if the name was already there or not
    def set_name_if_unset(self, key):
        try:
            self.db.Get(key, fill_cache=False)
        except KeyError:
            self.db.Put(key, '')
            logger.debug('TS propagating a new key', key, part='ts')
            # now propagate the key to the other ts nodes
            gossiper.stack_new_ts_broadcast(key)
        return False
    
    
    # List all keys in our name db that match the begining of key
    def list_keys(self, key):
        if key:
            start = key
            l = chr(ord(key[-1]) + 1)
            end = key[:-1] + l
            print "LOOKUP from %s to %s" % (start, end)
            r = self.db.RangeIter(start, end, include_value=False, fill_cache=False)
        else:  # Full scan? are you crazy?
            print "LOOKUP full scan"
            r = self.db.RangeIter(include_value=False, fill_cache=False)
        return list(r)
    
    
    # We consume data and create a new data entry if need
    def add_value(self, t, key, v):
        # be sure to work with int time
        t = int(t)
        
        T0 = time.time()
        STATS.incr('ts-add-value', 1)
        
        # Try to get the minute memory element. If not available, create one and
        # set it's creation time so the ts-reaper thread can grok it and archive it if too old
        e = self.data.get('min::%s' % key, None)
        if e is None:
            now = NOW.now  # int(time.time())
            e = {'cur_min': 0, 'sum': 0, 'min': None, 'max': None, 'values': [None] * 60, 'nb': 0, 'ctime': now}
            self.data['min::%s' % key] = e
            
            # Maybe we did not know about it, maybe so, but whatever, we add it
            self.set_name_if_unset(key)
        
        # Compute the minute start and the second idx inside the
        # minute (0-->59)
        _div = divmod(t, 60)
        t_minu = _div[0] * 60
        t_second = _div[1]
        
        # If we just changed the second
        if t_minu != e['cur_min']:
            # we don't save the first def_e
            if e['cur_min'] != 0:
                self.archive_minute(e, key)
            now = NOW.now  # int(time.time())
            e = {'cur_min': t_minu, 'sum': 0, 'min': None, 'max': None, 'values': [None] * 60, 'nb': 0, 'ctime': now}
            self.data['min::%s' % key] = e
        
        # We will insert the value at the t_second position, we are sure this place is
        # available as the structure is already filled when the dict is created
        e['values'][t_second] = v
        
        # Check if the new value change the min/max entry
        e_min = e['min']
        e_max = e['max']
        if not e_min or v < e_min:
            e['min'] = v
        if not e_max or v > e_max:
            e['max'] = v
        
        # And sum up the result so we will be able to compute the
        # avg entry
        e['sum'] += v
        e['nb'] += 1
        
        STATS.timer('ts.add_value', (time.time() - T0) * 1000)
    
    
    # Main function for writing in the DB the minute that just
    # finished, update the hour/day entry too, and if need save
    # them too
    def archive_minute(self, e, ID):
        STATS.incr('ts-archive-minute', 1)
        T0 = time.time()
        
        cur_min = e['cur_min']
        name = ID
        values = e['values']
        
        e['avg'] = None
        if e['nb'] != 0:
            e['avg'] = e['sum'] / float(e['nb'])
        
        # the main key we use to save the minute entry in the DB
        key = '%s::m%d' % (name, cur_min)
        
        # Serialize and put the value
        _t = time.time()
        ser = SERIALIZER.dumps(e, 2)
        STATS.incr('serializer', time.time() - _t)
        # We keep minutes for 1 day
        _t = time.time()
        self.push_key(key, ser, ttl=86400)
        STATS.incr('put-key', time.time() - _t)
        
        # Also insert the key in a time switching database
        # (one database by hour)
        # _t = time.time()
        # self.its.assume_key(key, cur_min)
        # STATS.incr('its-assume-key', time.time() - _t)
        
        
        ### Hour now
        # Now look at if we just switch hour
        hour = divmod(cur_min, 3600)[0] * 3600
        key = '%s::h%d' % (name, hour)
        
        # CUR_H_KEY = ALL[ID]['CUR_H_KEY']
        hour_e = self.data.get('hour::%s' % name, None)
        if hour_e is None:
            hour_e = {'hour': 0, 'sum': 0, 'min': None, 'max': None, 'values': [None] * 60, 'nb': 0}
            self.data['hour::%s' % name] = hour_e
        old_hour = hour_e['hour']
        # If we switch to a new hour and we are not the first def_hour value
        # we must save the hour entry in the database
        if hour != old_hour:
            if hour_e['hour'] != 0:
                _t = time.time()
                ser = SERIALIZER.dumps(hour_e)
                STATS.incr('serializer', time.time() - _t)
                
                # the main key we use to save the hour entry in the DB
                hkey = '%s::h%d' % (name, old_hour)
                
                # Keep hour thing for 1 month
                _t = time.time()
                self.push_key(key, ser, ttl=86400 * 31)
                STATS.incr('put-hour', time.time() - _t)
            
            # Now new one with the good hour of t :)
            hour_e = {'hour': 0, 'sum': 0, 'min': None, 'max': None, 'values': [None] * 60, 'nb': 0}
            hour_e['hour'] = hour
            self.data['hour::%s' % name] = hour_e
        
        _t = time.time()
        # Now compute the hour object update
        h_min = hour_e['min']
        h_max = hour_e['max']
        if h_min is None or e['min'] < h_min:
            hour_e['min'] = e['min']
        if h_max is None or e['max'] > h_max:
            hour_e['max'] = e['max']
        
        if e['avg'] is not None:
            hour_e['nb'] += 1
            hour_e['sum'] += e['avg']
            # We try to look at which minute we are in the hour object
            minute_hour_idx = (cur_min - hour) / 60
            hour_e['values'][minute_hour_idx] = e['avg']
            hour_e['avg'] = hour_e['sum'] / float(hour_e['nb'])
        STATS.incr('hour-compute', time.time() - _t)
        
        ### Day now
        # Now look at if we just switch day
        day = divmod(cur_min, 86400)[0] * 86400
        hkey = '%s::d%d' % (name, day)
        
        # Get the in-memory entry, and if none a default one
        day_e = self.data.get('day::%s' % hkey, None)
        if day_e is None:
            day_e = {'day': 0, 'sum': 0, 'min': None, 'max': None, 'values': [None] * 1440, 'nb': 0}
        old_day = day_e['day']
        # If we switch to a new day and we are not the first def_day value
        # we must save the day entry in the database
        if day != old_day and day_e['day'] != 0:
            _t = time.time()
            ser = SERIALIZER.dumps(day_e)
            STATS.incr('serializer', time.time() - _t)
            
            _t = time.time()
            # And keep day object for 1 year
            self.push_key(hkey, ser, ttl=86400 * 366)
            STATS.incr('put-day', time.time() - _t)
            
            # Now new one :)
            day_e = {'day': day, 'sum': 0, 'min': None, 'max': None, 'values': [None] * 1440, 'nb': 0}
            self.data['day::%s' % key] = day_e
        
        _t = time.time()
        # Now compute the day object update
        h_min = day_e['min']
        h_max = day_e['max']
        if h_min is None or e['min'] < h_min:
            day_e['min'] = e['min']
        if h_max is None or e['max'] > h_max:
            day_e['max'] = e['max']
        if e['avg'] is not None:
            day_e['nb'] += 1
            day_e['sum'] += e['avg']
            # We try to look at which minute we are in the day object
            minute_day_idx = (cur_min - day) / 60
            day_e['values'][minute_day_idx] = e['avg']
            day_e['avg'] = day_e['sum'] / float(day_e['nb'])
        STATS.incr('day-compute', time.time() - _t)
        
        STATS.timer('ts.archive-minute', (time.time() - T0) * 1000)
    
    
    # The reaper thread look at old minute objects that are not updated since long, and
    # force to archive them
    def launch_reaper_thread(self):
        threader.create_and_launch(self.do_reaper_thread, name='TS-reaper-thread', essential=True)
    
    
    def do_reaper_thread(self):
        while True:
            now = int(time.time())
            m = divmod(now, 60)[0] * 60  # current minute
            
            all_names = []
            with self.data_lock:
                all_names = self.data.keys()
            logger.debug("DOING reaper thread on %d elements" % len(all_names), part='ts')
            for name in all_names:
                # Grok all minute entries
                if name.startswith('min::'):
                    e = self.data.get(name, None)
                    # maybe some one delete the entry? should not be possible
                    if e is None:
                        continue
                    ctime = e['ctime']
                    logger.debug("REAPER old data for ", name, part='ts')
                    # if the creation time of this structure is too old and
                    # really for data, force to save the entry in KV entry
                    if ctime < now - self.max_data_age and e['nb'] > 0:
                        STATS.incr('reaper-old-data', 1)
                        logger.debug("REAPER TOO OLD DATA FOR", name, part='ts')
                        # get the raw metric name
                        _id = name[5:]
                        self.archive_minute(e, _id)
                        # the element was too old, so we can assume it won't be upadte again. Delete it's entry
                        try:
                            del self.data[name]
                        except:
                            pass
                        '''
                        # and set a new minute, the next one
                        n_minute = e['cur_min'] + 60
                        e = {'cur_min':n_minute, 'sum':0, 'min':None, 'max':None,
                             'values':[None for _ in xrange(60)], 'nb':0, 'ctime':now}
                        self.data[name] = e
                        '''
            time.sleep(10)
    
    
    # Export end points to get/list TimeSeries
    def export_http(self):
        @route('/list/')
        @route('/list/:key')
        def get_ts_keys(key=''):
            response.content_type = 'application/json'
            return json.dumps(tsmgr.list_keys(key))
        
        
        @route('/_ui_list/')
        @route('/_ui_list/:key')
        def get_ts_keys(key=''):
            response.content_type = 'application/json'
            print "LIST GET TS FOR KEY", key
            response.content_type = 'application/json'
            
            r = []
            keys = tsmgr.list_keys(key)
            l = len(key)
            added = {}
            for k in keys:
                print "LIST KEY", k
                title = k[l:]
                # maybe we got a key that do not belong to us
                # like srv-linux10 when we ask for linux1
                # so if we don't got a . here, it's an invalid
                # dir
                print "LIST TITLE", title
                if key and not title.startswith('.'):
                    print "LIST SKIPPING KEY", key
                    continue
                if title.startswith('.'):
                    title = title[1:]
                print "LIST TITLE CLEAN", title
                # if there is a . in it, it's a dir we need to have
                dname = title.split('.', 1)[0]
                # If the dname was not added, do it
                if dname not in added and title.count('.') != 0:
                    added[dname] = True
                    r.append({'title': dname, 'key': k[:l] + dname, 'folder': True, 'lazy': True})
                    print "LIST ADD DIR", dname, k[:l] + dname
                
                print "LIST DNAME KEY", dname, key, title.count('.')
                if title.count('.') == 0:
                    # not a directory, add it directly but only if the
                    # key asked was our directory
                    r.append({'title': title, 'key': k, 'folder': False, 'lazy': False})
                    print "LIST ADD FILE", title
            print "LIST FINALLY RETURN", r
            return json.dumps(r)


# TODO: this class is useless, we need to remove it and put statsd/graphite into their own modules
# that are using TsBackend
class TSListener(object):
    def __init__(self):
        self.addr = '0.0.0.0'
        self.statsd_port = 8125
        self.graphite_port = 2003
        self.last_write = time.time()
        self.nb_data = 0
        self.stats_interval = 10
        
        # Our real database manager
        self.tsb = TSBackend()
        
        # Do not step on your own foot...
        self.stats_lock = threading.RLock()
        
        # our main data structs
        self.gauges = {}
        self.timers = {}
        self.histograms = {}
        self.counters = {}
        
        # Graphite reaping queue
        self.graphite_queue = []
    
    
    def start_threads(self):
        # our helper objects
        # self.its = IdxTSDatabase()
        
        
        # Now start our threads
        # STATSD
        threader.create_and_launch(self.launch_statsd_udp_listener, name='TSL_statsd_thread', essential=True)
        threader.create_and_launch(self.launch_compute_stats_thread, name='TSC_thread', essential=True)
        # GRAPHITE
        threader.create_and_launch(self.launch_graphite_udp_listener, name='TSL_graphite_udp_thread', essential=True)
        threader.create_and_launch(self.launch_graphite_tcp_listener, name='TSL_graphite_tcp_thread', essential=True)
        
        threader.create_and_launch(self.graphite_reaper, name='graphite-reaper-thread', essential=True)
    
    
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
        logger.debug("Computing stats", part='ts')
        names = []
        
        # First gauges, we take the data and put a void dict instead so the other thread can work now
        with self.stats_lock:
            gauges = self.gauges
            self.gauges = {}
        
        for mname in gauges:
            _sum, nb, _min, _max = gauges[mname]
            _avg = _sum / float(nb)
            key = 'stats.gauges.' + mname
            self.tsb.add_value(now, key, _avg)
            key = 'stats.gauges.' + mname + '.min'
            self.tsb.add_value(now, key, _min)
            key = 'stats.gauges.' + mname + '.max'
            self.tsb.add_value(now, key, _max)
        
        # Now counters
        with self.stats_lock:
            counters = self.counters
            self.counters = {}
        
        for mname in counters:
            cvalue, ccount = counters[mname]
            # count
            key = 'stats.gauges.' + mname + '.count'
            self.tsb.add_value(now, key, cvalue)
            # rate
            key = 'stats.gauges.' + mname + '.rate'
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
            key = 'stats.timers.' + mname + '.mean'
            self.tsb.add_value(now, key, mean)
            
            # Upper 99th, percentile
            upper_99 = np.percentile(npvalues, 99)
            key = 'stats.timers.' + mname + '.upper_99'
            self.tsb.add_value(now, key, upper_99)
            
            # Sum 99
            sum_99 = npvalues[:(npvalues < upper_99).argmin()].sum()
            key = 'stats.timers.' + mname + '.sum_99'
            self.tsb.add_value(now, key, sum_99)
            
            # Standard deviation
            std = np.std(npvalues)
            key = 'stats.timers.' + mname + '.std'
            self.tsb.add_value(now, key, std)
            
            # Simple count
            count = len(timer)
            key = 'stats.timers.' + mname + '.count'
            self.tsb.add_value(now, key, count)
            
            # Sum of all
            _sum = np.sum(npvalues)
            key = 'stats.timers.' + mname + '.sum'
            self.tsb.add_value(now, key, _sum)
            
            # Median of all
            median = np.percentile(npvalues, 50)
            key = 'stats.timers.' + mname + '.median'
            self.tsb.add_value(now, key, median)
            
            # Upper of all
            upper = np.max(npvalues)
            key = 'stats.timers.' + mname + '.upper'
            self.tsb.add_value(now, key, upper)
            
            # Lower of all
            lower = np.min(npvalues)
            key = 'stats.timers.' + mname + '.lower'
            self.tsb.add_value(now, key, lower)
    
    
    # This is ht main STATSD UDP listener thread. Should not block and
    # be as fast as possible
    def launch_statsd_udp_listener(self):
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logger.debug(self.udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF), part='ts')
        self.udp_sock.bind((self.addr, self.statsd_port))
        logger.info("TS UDP port open", self.statsd_port, part='ts')
        logger.debug("UDP RCVBUF", self.udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF), part='ts')
        while not stopper.interrupted:
            try:
                data, addr = self.udp_sock.recvfrom(65535)  # buffer size is 1024 bytes
            except socket.timeout:  # loop until we got something
                continue
            
            logger.debug("UDP: received message:", data, addr, part='ts')
            # No data? bail out :)
            if len(data) == 0:
                continue
            logger.debug("GETDATA", data, part='ts')
            
            for line in data.splitlines():
                # avoid invalid lines
                if '|' not in line:
                    continue
                elts = line.split('|', 1)
                # invalid, no type in the right part
                if len(elts) == 1:
                    continue
                
                _name_value = elts[0].strip()
                # maybe it's an invalid name...
                if ':' not in _name_value:
                    continue
                _nvs = _name_value.split(':')
                if len(_nvs) != 2:
                    continue
                mname = _nvs[0].strip()
                
                # Two cases: it's for me or not
                hkey = hashlib.sha1(mname).hexdigest()
                ts_node_manager = gossiper.find_tag_node('ts', hkey)
                # if it's me that manage this key, I add it in my backend
                if ts_node_manager != gossiper.uuid:
                    node = gossiper.get(ts_node_manager)
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
                    logger.log('GAUGE', mname, value)
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
                        logger.debug('NEW GAUGE', mname, self.gauges[mname], part='ts')
                
                ## Timers: <metric name>:<value>|ms
                ## But also
                ## Histograms: <metric name>:<value>|h
                elif _type == 'ms' or _type == 'h':
                    logger.debug('timers', mname, value, part='ts')
                    # TODO: avoid the SET each time
                    timer = self.timers.get(mname, [])
                    timer.append(value)
                    self.timers[mname] = timer
                ## Counters: <metric name>:<value>|c[|@<sample rate>]
                elif _type == 'c':
                    self.nb_data += 1
                    logger.info('COUNTER', mname, value, "rate", 1, part='ts')
                    with self.stats_lock:
                        cvalue, ccount = self.counters.get(mname, (0, 0))
                        self.counters[mname] = (cvalue + value, ccount + 1)
                        logger.debug('NEW COUNTER', mname, self.counters[mname], part='ts')
                        ## Meters: <metric name>:<value>|m
                elif _type == 'm':
                    logger.debug('METERs', mname, value, part='ts')
                else:  # unknow type, maybe a c[|@<sample rate>]
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
                        logger.debug('COUNTER', mname, value, "rate", rate, part='ts')
                        with self.stats_lock:
                            cvalue, ccount = self.counters.get(mname, (0, 0))
                            logger.debug('INCR counter', (value / rate), part='ts')
                            self.counters[mname] = (cvalue + (value / rate), ccount + 1 / rate)
                            logger.debug('NEW COUNTER', mname, self.counters[mname], part='ts')
    
    
    # Thread for listening to the graphite port in UDP (2003)
    def launch_graphite_udp_listener(self):
        self.graphite_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.graphite_udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.graphite_udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        logger.log(self.graphite_udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
        self.graphite_udp_sock.bind((self.addr, self.graphite_port))
        logger.info("TS Graphite UDP port open", self.graphite_port, part='ts')
        logger.debug("UDP RCVBUF", self.graphite_udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF), part='ts')
        while not stopper.interrupted:
            try:
                data, addr = self.graphite_udp_sock.recvfrom(65535)
            except socket.timeout:  # loop until we got some data
                continue
            logger.debug("UDP Graphite: received message:", len(data), addr, part='ts')
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
        logger.info("TS Graphite TCP port open", self.graphite_port, part='ts')
        while not stopper.interrupted:
            try:
                conn, addr = self.graphite_tcp_sock.accept()
            except socket.timeout:  # loop until we got some connect
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
                data += ldata[:lst_nidx + 1]
                STATS.incr('ts.graphite.tcp.receive', 1)
                self.graphite_queue.append(data)
                # stack the data with the garbage so we will continue it
                # on the next turn
                data = ldata[lst_nidx + 1:]
            conn.close()
            # Also stack what the last send
            self.graphite_queue.append(data)
    
    
    # Main graphite reaper thread, that will get data from both tcp and udp flow
    # and dispatch it to the others daemons if need
    def graphite_reaper(self):
        while not stopper.interrupted:
            graphite_queue = self.graphite_queue
            self.graphite_queue = []
            if len(graphite_queue) > 0:
                logger.info("Graphite queue", len(graphite_queue))
            for data in graphite_queue:
                T0 = time.time()
                self.grok_graphite_data(data)
                STATS.timer('ts.graphite.grok-graphite-data', (time.time() - T0) * 1000)
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
            ts_node_manager = gossiper.find_tag_node('ts', hkey)
            # if it's me that manage this key, I add it in my backend
            if ts_node_manager == gossiper.uuid:
                logger.debug("I am the TS node manager", part='ts')
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
                logger.debug("The node manager for this Ts is ", ts_node_manager, part='ts')
                l = forwards.get(ts_node_manager, [])
                l.append(line)
                forwards[ts_node_manager] = l
        
        for (uuid, lst) in forwards.iteritems():
            node = gossiper.get(uuid)
            # maybe the node disapear? bail out, we are not lucky
            if node is None:
                continue
            packets = []
            # first compute the packets
            buf = ''
            for line in lst:
                buf += line + '\n'
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


tsmgr = TSListener()
