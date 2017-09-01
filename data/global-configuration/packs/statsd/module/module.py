import time
import socket
import hashlib
import threading

from opsbro.util import to_best_int_float

from opsbro.gossip import gossiper

# DO NOT FORGEET:
# sysctl -w net.core.rmem_max=26214400


from opsbro.threadmgr import threader
from opsbro.module import ListenerModule
from opsbro.stop import stopper
from opsbro.ts import tsmgr
from opsbro.parameters import StringParameter, BoolParameter, IntParameter


class StatsdModule(ListenerModule):
    implement = 'statsd'
    
    parameters = {
        'enabled' : BoolParameter(default=False),
        'port'    : IntParameter(default=8125),
        'interval': IntParameter(default=10),
        'address' : StringParameter(default='0.0.0.0'),
    }
    
    
    def __init__(self):
        ListenerModule.__init__(self)
        self.statsd = None
        self.enabled = False
        self.port = 0
        self.udp_sock = None
        self.addr = '0.0.0.0'
        self.last_write = time.time()
        self.nb_data = 0
        
        # Do not step on your own foot...
        self.stats_lock = threading.RLock()
        
        # our main data structs
        self.gauges = {}
        self.timers = {}
        self.histograms = {}
        self.counters = {}
        
        # Numpy lib is heavy, don't load it unless we really need it
        self.np = None
    
    
    # Prepare to open the UDP port
    def prepare(self):
        self.logger.debug('Statsd: prepare phase')
        
        self.enabled = self.get_parameter('enabled')
        self.statsd_port = self.get_parameter('port')
        self.stats_interval = self.get_parameter('interval')
        self.addr = self.get_parameter('address')
        
        if self.enabled:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.logger.debug(self.udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
            self.udp_sock.bind((self.addr, self.statsd_port))
            self.logger.info("TS UDP port open", self.statsd_port)
            self.logger.debug("UDP RCVBUF", self.udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
            import numpy as np
            self.np = np
        else:
            self.logger.info('STATSD is not enabled, skipping it')
    
    
    def get_info(self):
        return {'statsd_configuration': self.get_config(), 'statsd_info': None}
    
    
    def launch(self):
        threader.create_and_launch(self.launch_statsd_udp_listener, name='UDP port:%d listening' % self.statsd_port, essential=True, part='statsd')
        threader.create_and_launch(self.launch_compute_stats_thread, name='Stats computing', essential=True, part='statsd')
    
    
    # The compute stats thread compute the STATSD values each X
    # seconds and push them into the classic TS part
    def launch_compute_stats_thread(self):
        while not stopper.interrupted:
            now = time.time()
            if now > self.last_write + self.stats_interval:
                self.compute_stats()
                self.last_write = now
            time.sleep(0.1)
    
    
    def compute_stats(self):
        now = int(time.time())
        self.logger.debug("Computing stats")
        
        # First gauges, we take the data and put a void dict instead so the other thread can work now
        with self.stats_lock:
            gauges = self.gauges
            self.gauges = {}
        
        for mname in gauges:
            _sum, nb, _min, _max = gauges[mname]
            _avg = _sum / float(nb)
            key = 'stats.gauges.' + mname
            tsmgr.tsb.add_value(now, key, _avg)
            key = 'stats.gauges.' + mname + '.min'
            tsmgr.tsb.add_value(now, key, _min)
            key = 'stats.gauges.' + mname + '.max'
            tsmgr.tsb.add_value(now, key, _max)
        
        # Now counters
        with self.stats_lock:
            counters = self.counters
            self.counters = {}
        
        for mname in counters:
            cvalue, ccount = counters[mname]
            # count
            key = 'stats.gauges.' + mname + '.count'
            tsmgr.tsb.add_value(now, key, cvalue)
            # rate
            key = 'stats.gauges.' + mname + '.rate'
            tsmgr.tsb.add_value(now, key, cvalue / self.stats_interval)
        
        # Now timers, lot of funs :)
        with self.stats_lock:
            timers = self.timers
            self.timers = {}
        
        _t = time.time()
        for (mname, timer) in timers.iteritems():
            # We will need to compute the mean_99, count_99, upper_99, sum_99, sum_quares_99
            # but also std, upper, lower, count, count_ps, sum, sum_square, mean, median
            _t = time.time()
            npvalues = self.np.array(timer)
            # Mean
            mean = self.np.mean(npvalues)
            key = 'stats.timers.' + mname + '.mean'
            tsmgr.tsb.add_value(now, key, mean)
            
            # Upper 99th, percentile
            upper_99 = self.np.percentile(npvalues, 99)
            key = 'stats.timers.' + mname + '.upper_99'
            tsmgr.tsb.add_value(now, key, upper_99)
            
            # Sum 99
            sum_99 = npvalues[:(npvalues < upper_99).argmin()].sum()
            key = 'stats.timers.' + mname + '.sum_99'
            tsmgr.tsb.add_value(now, key, sum_99)
            
            # Standard deviation
            std = self.np.std(npvalues)
            key = 'stats.timers.' + mname + '.std'
            tsmgr.tsb.add_value(now, key, std)
            
            # Simple count
            count = len(timer)
            key = 'stats.timers.' + mname + '.count'
            tsmgr.tsb.add_value(now, key, count)
            
            # Sum of all
            _sum = self.np.sum(npvalues)
            key = 'stats.timers.' + mname + '.sum'
            tsmgr.tsb.add_value(now, key, _sum)
            
            # Median of all
            median = self.np.percentile(npvalues, 50)
            key = 'stats.timers.' + mname + '.median'
            tsmgr.tsb.add_value(now, key, median)
            
            # Upper of all
            upper = self.np.max(npvalues)
            key = 'stats.timers.' + mname + '.upper'
            tsmgr.tsb.add_value(now, key, upper)
            
            # Lower of all
            lower = self.np.min(npvalues)
            key = 'stats.timers.' + mname + '.lower'
            tsmgr.tsb.add_value(now, key, lower)
    
    
    # This is ht main STATSD UDP listener thread. Should not block and
    # be as fast as possible
    def launch_statsd_udp_listener(self):
        while not stopper.interrupted:
            if not self.enabled:
                # Maybe we was enabled, and we are no more:
                if self.udp_sock:
                    self.udp_sock.close()
                    self.udp_sock = None
                time.sleep(1)
                continue
            # maybe we were enabled, then not, then again, if so re-prepare
            if self.udp_sock is None:
                self.prepare()
            try:
                data, addr = self.udp_sock.recvfrom(65535)  # buffer size is 1024 bytes
            except socket.timeout:  # loop until we got something
                continue
            
            self.logger.debug("UDP: received message:", data, addr)
            # No data? bail out :)
            if len(data) == 0:
                continue
            self.logger.debug("GETDATA", data)
            
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
                ts_node_manager = gossiper.find_group_node('ts', hkey)
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
                    self.logger.log('GAUGE', mname, value)
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
                        self.logger.debug('NEW GAUGE', mname, self.gauges[mname])
                
                ## Timers: <metric name>:<value>|ms
                ## But also
                ## Histograms: <metric name>:<value>|h
                elif _type == 'ms' or _type == 'h':
                    self.logger.debug('timers', mname, value)
                    # TODO: avoid the SET each time
                    timer = self.timers.get(mname, [])
                    timer.append(value)
                    self.timers[mname] = timer
                ## Counters: <metric name>:<value>|c[|@<sample rate>]
                elif _type == 'c':
                    self.nb_data += 1
                    self.logger.info('COUNTER', mname, value, "rate", 1)
                    with self.stats_lock:
                        cvalue, ccount = self.counters.get(mname, (0, 0))
                        self.counters[mname] = (cvalue + value, ccount + 1)
                        self.logger.debug('NEW COUNTER', mname, self.counters[mname])
                        ## Meters: <metric name>:<value>|m
                elif _type == 'm':
                    self.logger.debug('METERs', mname, value)
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
                        self.logger.debug('COUNTER', mname, value, "rate", rate)
                        with self.stats_lock:
                            cvalue, ccount = self.counters.get(mname, (0, 0))
                            self.logger.debug('INCR counter', (value / rate))
                            self.counters[mname] = (cvalue + (value / rate), ccount + 1 / rate)
                            self.logger.debug('NEW COUNTER', mname, self.counters[mname])
