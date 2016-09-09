import time
import json
from kunai.log import logger
from kunai.httpdaemon import route, response
from kunai.evaluater import evaluater
from kunai.collectormanager import collectormgr

class DetectorMgr(object):
    def __init__(self):
        self.clust = None
        self.did_run = False  # did we run at least once? so are our tags ok currently?
        
    
    def load(self, clust):
        self.clust = clust
    
    
    # Main thread for launching detectors
    def do_detector_thread(self):
        # if the collector manager did not run, our evaluation can be invalid, so wait for all collectors to run at least once
        while collectormgr.did_run == False:
            time.sleep(1)
        # Ok we can use collector data :)
        logger.log('DETECTOR thread launched', part='detector')
        while not self.clust.interrupted:
            for (gname, gen) in self.clust.detectors.iteritems():
                interval = int(gen['interval'].split('s')[0])  # todo manage like it should
                should_be_launch = gen['last_launch'] < int(time.time()) - interval
                if should_be_launch:
                    gen['last_launch'] = int(time.time())
                    try:
                        do_apply = evaluater.eval_expr(gen['apply_if'])
                    except Exception, exp:
                        logger.error('Cannot execute detector %s: %s' % (gname, exp), part='detector')
                        do_apply = False
                    if do_apply:
                        tags = gen['tags']
                        logger.debug('Tags %s are applying' % tags, part='detector')
                        for tag in tags:
                            if tag not in self.clust.tags:
                                logger.info("New tag detected for this node: %s" % tag, part='detector')
                                self.clust.tags.append(tag)
            
            self.did_run = True  # ok we did detect our tags, we can be sure about us
            time.sleep(1)
            
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        
        @route('/agent/detectors/')
        @route('/agent/detectors')
        def get_detectors():
            response.content_type = 'application/json'
            return json.dumps(self.clust.detectors.values())
        
        
        @route('/agent/detectors/run')
        @route('/agent/detectors/run/:dname')
        def _runrunrunr(dname=''):
            response.content_type = 'application/json'
            res = {}
            for (gname, gen) in self.clust.detectors.iteritems():
                if dname and dname != gname:
                    continue
                res[gname] = {'matched': False, 'tags': [], 'new_tags': []}
                print "LAUNCHING DETECTOR", gen
                try:
                    res[gname]['matched'] = evaluater.eval_expr(gen['apply_if'])
                except Exception, exp:
                    logger.error('Cannot execute detector %s: %s' % (gname, exp), part='detector')
                    res[gname]['matched'] = False
                if res[gname]['matched']:
                    res[gname]['tags'] = gen['tags']
                    for tag in res[gname]['tags']:
                        if tag not in self.clust.tags:
                            res[gname]['new_tags'].append(tag)
                            print "ADDING NEW TAGS", tag
            
            return json.dumps(res)


detecter = DetectorMgr()
