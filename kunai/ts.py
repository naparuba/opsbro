import os
import time
import threading
import base64
import cPickle
import json

from kunai.stats import STATS
from kunai.log import LoggerFactory
from kunai.threadmgr import threader
from kunai.now import NOW
from kunai.dbwrapper import dbwrapper
from kunai.gossip import gossiper
from kunai.stop import stopper
from kunai.kv import kvmgr
from kunai.httpdaemon import http_export, response

# DO NOT FORGEET:
# sysctl -w net.core.rmem_max=26214400

SERIALIZER = cPickle

# Global logger for this part
logger = LoggerFactory.create_logger('time-series')


class TSBackend(object):
    def __init__(self):
        self.data = {}
        self.data_lock = threading.RLock()
        self.max_data_age = 5 * 60  # number of seconds before an entry is declared too old and is forced archived
    
    
    # When we load, really open our database
    def load(self, data_dir):
        # Get a db with all our metrics listed
        # We will save all the metrics we have
        self.db_dir = os.path.join(data_dir, 'ts')
        self.db = dbwrapper.get_db(self.db_dir)
        # Ok start our inner thread
        self.launch_reaper_thread()
    
    
    def push_key(self, k, v, ttl=0, local=False):
        T0 = time.time()
        STATS.incr('ts.graphite.push-key', 1)
        v64 = base64.b64encode(v)
        logger.debug("PUSH KEY", k, "and value", len(v64))
        # If we manage a local data (from collectors), manage directly
        kvmgr.stack_put_key(k, v64, ttl=ttl, force=local)
        STATS.timer('ts.graphite.push-key', (time.time() - T0) * 1000)
        return
    
    
    # push a name but return if the name was already there or not
    def set_name_if_unset(self, key):
        try:
            self.db.Get(key, fill_cache=False)
        except KeyError:
            self.db.Put(key, '')
            logger.debug('TS propagating a new key', key)
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
    def add_value(self, t, key, v, local=False):
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
                self.archive_minute(e, key, local=local)
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
    def archive_minute(self, e, ID, local):
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
        self.push_key(key, ser, ttl=86400, local=local)
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
                self.push_key(key, ser, ttl=86400 * 31, local=local)
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
            self.push_key(hkey, ser, ttl=86400 * 366, local=local)
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
        threader.create_and_launch(self.do_reaper_thread, name='Metric reaper', essential=True, part='time-series')
    
    
    def do_reaper_thread(self):
        while not stopper.interrupted:
            now = NOW.now

            with self.data_lock:
                all_names = self.data.keys()
            logger.debug("DOING reaper thread on %d elements" % len(all_names))
            for name in all_names:
                # Grok all minute entries
                if name.startswith('min::'):
                    e = self.data.get(name, None)
                    # maybe some one delete the entry? should not be possible
                    if e is None:
                        continue
                    ctime = e['ctime']
                    # if the creation time of this structure is too old and
                    # really for data, force to save the entry in KV entry
                    if ctime < now - self.max_data_age and e['nb'] > 0:
                        STATS.incr('reaper-old-data', 1)
                        logger.debug("REAPER TOO OLD DATA FOR", name)
                        # get the raw metric name
                        _id = name[5:]
                        self.archive_minute(e, _id, local=True)
                        # the element was too old, so we can assume it won't be update again. Delete it's entry
                        try:
                            del self.data[name]
                        except:
                            pass

            time.sleep(10)
    
    
    # Export end points to get/list TimeSeries
    def export_http(self):
        @http_export('/list/')
        @http_export('/list/:key')
        def get_ts_keys(key=''):
            response.content_type = 'application/json'
            return json.dumps(tsmgr.list_keys(key))
        
        
        @http_export('/_ui_list/')
        @http_export('/_ui_list/:key')
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
        # Our real database manager
        self.tsb = TSBackend()
    
    
    def start_threads(self):
        pass
    
    
    # push a name but return if the name was already there or not
    def set_name_if_unset(self, key):
        return self.tsb.set_name_if_unset(key)
    
    
    # list all keys that start with key
    def list_keys(self, key):
        return self.tsb.list_keys(key)


tsmgr = TSListener()
