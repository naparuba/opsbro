import os
import time
import traceback
import random
import threading
import glob
import imp
import copy
import json

from .log import LoggerFactory
from .threadmgr import threader
from .stop import stopper
from .httpdaemon import http_export, response
from .collector import Collector
from .jsonmgr import jsoner
from .now import NOW
from .ts import tsmgr
from .gossip import gossiper
from .basemanager import BaseManager

# Global logger for this part
logger = LoggerFactory.create_logger('collector')

# Common rule for printing the COLLECTORS for the outside world
COLLECTORS_STATE_COLORS = {'OK': 'green', 'ERROR': 'red', 'NOT-ELIGIBLE': 'grey', 'RUNNING': 'grey', 'PENDING': 'grey'}
COLLECTORS_STATES = ['PENDING', 'OK', 'NOT-ELIGIBLE', 'RUNNING', 'ERROR']


def get_collectors(self):
    collector_dir = os.path.dirname(__file__)
    p = collector_dir + '/collectors/*py'
    logger.debug('Loading collectors from path:', p)
    collector_files = glob.glob(p)
    for f in collector_files:
        fname = os.path.splitext(os.path.basename(f))[0]
        try:
            imp.load_source('collector%s' % fname, f)
        except Exception as exp:
            logger.error('Cannot load collector %s: %s' % (fname, exp))
            continue
    
    self.load_all_collectors()


class CollectorManager(BaseManager):
    history_directory_suffix = 'collector'
    
    
    def __init__(self):
        super(CollectorManager, self).__init__()
        self.collectors = {}
        
        self.did_run = False  # did our data are all ok or we did not launch all?
        
        # results from the collectors, keep ony the last run
        self.results_lock = threading.RLock()
        self.results = {}
        
        self.logger = logger
    
    
    def load_directory(self, directory, pack_name='', pack_level=''):
        logger.debug('Loading collector directory at %s for pack %s' % (directory, pack_name))
        pth = directory + '/collector_*.py'
        collector_files = glob.glob(pth)
        for f in collector_files:
            fname = os.path.splitext(os.path.basename(f))[0]
            logger.debug('Loading collector from file %s' % f)
            try:
                # NOTE: KEEP THE ___ as they are used to let the class INSIDE te module in which pack/level they are. If you have
                # another way to give the information to the inner class inside, I take it ^^
                m = imp.load_source('collector___%s___%s___%s' % (pack_level, pack_name, fname), f)
                logger.debug('Collector module loaded: %s' % m)
            except Exception as exp:
                logger.error('Cannot load collector %s: %s' % (fname, exp))
    
    
    def load_all_collectors(self):
        collector_clss = Collector.get_sub_class()
        for ccls in collector_clss:
            # skip base module Collector
            if ccls == Collector:
                continue
            
            # Maybe this collector is already loaded
            if ccls in self.collectors:
                continue
            
            self.load_collector(ccls)
    
    
    def load_collector(self, cls):
        colname = cls.__name__.lower()
        
        # If already loaded, skip it
        if colname in self.collectors:
            return
        
        logger.debug('Loading collector %s from class %s, from pack %s and from pack level %s' % (colname, cls, cls.pack_name, cls.pack_level))
        try:
            # also give it our put result callback
            inst = cls()
        except Exception as exp:
            logger.error('Cannot load the %s collector: %s' % (cls, traceback.format_exc()))
            return
        
        e = {
            'name'      : colname,
            'inst'      : inst,
            'last_check': 0,
            'next_check': int(time.time()) + int(random.random()) * 10,
            'results'   : None,
            'metrics'   : None,
            'active'    : False,
            'log'       : '',
        }
        self.collectors[colname] = e
    
    
    # Now we hae our collectors and our parameters, link both
    def get_parameters_from_packs(self):
        for (cname, e) in self.collectors.items():
            e['inst'].get_parameters_from_pack()
    
    
    def load_collectors(self):
        get_collectors(self)
    
    
    def get_info(self):
        res = {}
        with self.results_lock:
            for (cname, e) in self.collectors.items():
                d = {'name': e['name'], 'state': e['inst'].state, 'log': e['inst'].log}
                res[cname] = d
        return res
    
    
    def get_retention(self):
        res = {}
        with self.results_lock:
            for (cname, e) in self.collectors.items():
                res[cname] = {}
                res[cname]['results'] = e['results']
                res[cname]['metrics'] = e['metrics']
                res[cname]['state'] = e['inst'].state
                res[cname]['old_state'] = e['inst'].old_state
        return res
    
    
    def load_retention(self, data):
        with self.results_lock:
            for (cname, e) in data.items():
                # maybe this collectr is missing now
                if cname not in self.collectors:
                    continue
                inst = self.collectors[cname]['inst']
                self.collectors[cname]['results'] = e['results']
                self.collectors[cname]['metrics'] = e['metrics']
                inst.state = e.get('state', 'PENDING')
                inst.old_state = e.get('old_state', 'PENDING')
    
    
    def get_data(self, s):
        elts = s.split('.')
        d = {}
        # construct will all results of our collectors
        for (k, v) in self.collectors.items():
            d[k] = v['results']
        
        for k in elts:
            if not isinstance(d, dict) or k not in d:
                raise KeyError('Cannot find %s key %s in %s' % (s, k, elts))
            d = d[k]
        # last is the good one
        return d
    
    
    # Our collector threads will put back results so beware of the threads
    def put_result(self, cname, results, metrics, log):
        logger.debug('[COLLECTOR] put result for %s: %s metrics' % (cname, len(metrics)), part='collector.%s' % cname)
        col = self.collectors.get(cname, None)
        
        # Maybe there is no more such collector?
        if col is None:
            return
        col = self.collectors[cname]
        col['log'] = log
        
        # Only set results and metrics if available
        if not results:
            col['active'] = False
            return
        
        col['results'] = results
        col['metrics'] = metrics
        col['active'] = True
        
        timestamp = NOW.now
        for (mname, value) in metrics:
            key = '%s.%s.%s' % (gossiper.name, cname, mname)
            if hasattr(tsmgr, 'tsb'):
                tsmgr.tsb.add_value(timestamp, key, value, local=True)
    
    
    # Main thread for launching collectors
    def do_collector_thread(self):
        logger.log('COLLECTOR thread launched')
        cur_launchs = {}
        # Before run, be sure we have a history directory ready
        self.prepare_history_directory()
        while not stopper.interrupted:
            now = int(time.time())
            for (colname, e) in self.collectors.items():
                colname = e['name']
                inst = e['inst']
                # maybe a collection is already running
                if colname in cur_launchs:
                    continue
                if now >= e['next_check']:
                    logger.debug('COLLECTOR: launching collector %s' % colname)
                    t = threader.create_and_launch(inst.main, name='collector-%s' % colname, part='collector')
                    cur_launchs[colname] = t
                    e['next_check'] += 10
                    e['last_check'] = now
            
            to_del = []
            for (colname, t) in cur_launchs.items():
                # if the thread is finish, join it
                # NOTE: but also wait for all first execution to finish
                if not t.is_alive() or not self.did_run:
                    logger.debug('Joining collector thread: %s' % colname)
                    t.join()
                    to_del.append(colname)
            for colname in to_del:
                del cur_launchs[colname]
            self.did_run = True  # ok our data are filled, you can use this data
            # Each loop we save our history data (collector state changed)
            self.write_history_entry()
            time.sleep(1)
    
    
    def get_collector_json_extract(self, entry):
        c = copy.copy(entry)
        inst = c['inst']
        c['state'] = inst.state
        c['log'] = inst.log
        # inst are not serializable
        del c['inst']
        return (c['name'], c)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        
        @http_export('/collectors/')
        @http_export('/collectors')
        #        @protected()
        def GET_collectors():
            response.content_type = 'application/json'
            res = {}
            for (ccls, e) in self.collectors.items():
                cname, c = self.get_collector_json_extract(e)
                res[cname] = c
            return jsoner.dumps(res)
        
        
        @http_export('/collectors/:_id')
        def GET_collector(_id):
            response.content_type = 'application/json'
            e = self.collectors.get(_id, None)
            if e is None:
                return jsoner.dumps(e)
            cname, c = self.get_collector_json_extract(e)
            return jsoner.dumps(c)
        
        
        @http_export('/agent/collectors/history', method='GET')
        def get_collectors_history():
            response.content_type = 'application/json'
            r = self.get_history()
            return json.dumps(r)


collectormgr = CollectorManager()
