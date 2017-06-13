import os
import time
import traceback
import random
import threading
import glob
import imp
import copy
from kunai.log import logger
from kunai.threadmgr import threader
from kunai.stop import stopper
from kunai.httpdaemon import route, response
from kunai.collector import Collector

from jsonmgr import jsoner


def get_collectors(self):
    collector_dir = os.path.dirname(__file__)
    p = collector_dir + '/collectors/*py'
    logger.debug('Loading collectors from path:', p, part='collector')
    collector_files = glob.glob(p)
    for f in collector_files:
        fname = os.path.splitext(os.path.basename(f))[0]
        try:
            imp.load_source('collector%s' % fname, f)
        except Exception, exp:
            logger.error('Cannot load collector %s: %s' % (fname, exp))
            continue
    
    self.load_all_collectors()




class CollectorManager:
    def __init__(self):
        self.collectors = {}
        self.interrupted = False
        self.cfg_data = {}
        
        self.did_run = False  # did our data are all ok or we did not launch all?
        
        # results from the collectors, keep ony the last run
        self.results_lock = threading.RLock()
        self.results = {}
        self.ts = None
        self.export_http()
    
    
    # Get the ts from the cluster
    def load_ts(self, ts):
        self.ts = ts
    
    
    def load_directory(self, directory, pack_name=''):
        logger.debug('Loading collector directory at %s for pack %s' % (directory, pack_name))
        pth = directory + '/collector_*.py'
        collector_files = glob.glob(pth)
        for f in collector_files:
            fname = os.path.splitext(os.path.basename(f))[0]
            logger.debug('Loading collector from file %s' % f)
            try:
                m = imp.load_source('collector_%s_%s' % (pack_name, fname), f)
                logger.debug('Collector module loaded: %s' % m)
            except Exception, exp:
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
        
        logger.debug('Loading collector %s from class %s' % (colname, cls))
        try:
            # also give it our put result callback
            inst = cls(self.cfg_data, put_result=self.put_result)
        except Exception, exp:
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
    
    
    def load_collectors(self, cfg_data):
        self.cfg_data = cfg_data
        logger.debug('Cfg data:%s' % cfg_data, part='collector')
        get_collectors(self)
    
    
    def get_info(self):
        res = {}
        with self.results_lock:
            for (cname, e) in self.collectors.iteritems():
                d = {'name': e['name'], 'active': e['active'], 'log': e['log']}
                res[cname] = d
        return res
    
    
    def get_retention(self):
        res = {}
        with self.results_lock:
            for (cname, e) in self.collectors.iteritems():
                res[cname] = {}
                res[cname]['results'] = e['results']
                res[cname]['metrics'] = e['metrics']
        return res
    
    
    def load_retention(self, data):
        with self.results_lock:
            for (cname, e) in data.iteritems():
                # maybe this collectr is missing now
                if cname not in self.collectors:
                    continue
                self.collectors[cname]['results'] = e['results']
                self.collectors[cname]['metrics'] = e['metrics']
    
    
    def get_data(self, s):
        elts = s.split('.')
        d = {}
        # construct will all results of our collectors
        for (k, v) in self.collectors.iteritems():
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
        
        # Only set results and metrics if availables
        if not results:
            col['active'] = False
            return
        
        col['results'] = results
        col['metrics'] = metrics
        col['active'] = True
        
        '''
        # TODO: get back TS data?
        timestamp = NOW.now
        for (mname, value) in metrics:
            key = '%s.%s.%s' % (tsmgr.get_name(), cname, mname)
            if hasattr(tsmgr, 'tsb'):
                tsmgr.tsb.add_value(timestamp, key, value)
        '''
    
    
    # Main thread for launching collectors
    def do_collector_thread(self):
        logger.log('COLLECTOR thread launched', part='collector')
        cur_launchs = {}
        while not stopper.interrupted:
            now = int(time.time())
            for (colname, e) in self.collectors.iteritems():
                colname = e['name']
                inst = e['inst']
                # maybe a collection is already running
                if colname in cur_launchs:
                    continue
                if now >= e['next_check']:
                    logger.debug('COLLECTOR: launching collector %s' % colname, part='collector')
                    t = threader.create_and_launch(inst.main, name='collector-%s' % colname)
                    cur_launchs[colname] = t
                    e['next_check'] += 10
                    e['last_check'] = now
            
            to_del = []
            for (colname, t) in cur_launchs.iteritems():
                if not t.is_alive():
                    t.join()
                    to_del.append(colname)
            for colname in to_del:
                del cur_launchs[colname]
            
            self.did_run = True  # ok our data are filled, you can use this data
            time.sleep(1)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        def prepare_entry(e):
            c = copy.copy(e)
            # inst are not serializable
            del c['inst']
            return (c['name'], c)
        
        
        @route('/collectors/')
        @route('/collectors')
        #        @protected()
        def GET_collectors():
            response.content_type = 'application/json'
            res = {}
            for (ccls, e) in self.collectors.iteritems():
                cname, c = prepare_entry(e)
                res[cname] = c
            return jsoner.dumps(res)
        
        
        @route('/collectors/:_id')
        def GET_container(_id):
            response.content_type = 'application/json'
            e = self.collectors.get(_id, None)
            if e is None:
                return jsoner.dumps(e)
            cname, c = prepare_entry(e)
            return jsoner.dumps(c)


collectormgr = CollectorManager()
