import time
import json

from kunai.log import LoggerFactory
from kunai.stop import stopper
from kunai.httpdaemon import http_export, response
from kunai.evaluater import evaluater
from kunai.collectormanager import collectormgr
from kunai.gossip import gossiper
from kunai.monitoring import monitoringmgr

# Global logger for this part
logger = LoggerFactory.create_logger('detector')


class DetectorMgr(object):
    def __init__(self):
        self.clust = None
        self.did_run = False  # did we run at least once? so are our tags ok currently?
        self.detected_tags = {}
    
    
    def load(self, clust):
        self.clust = clust
    
    
    # Main thread for launching detectors
    def do_detector_thread(self):
        # if the collector manager did not run, our evaluation can be invalid, so wait for all collectors to run at least once
        while collectormgr.did_run == False:
            time.sleep(1)
        # Ok we can use collector data :)
        logger.log('DETECTOR thread launched')
        while not stopper.interrupted:
            matching_tags = set()
            for (gname, gen) in self.clust.detectors.iteritems():
                interval = int(gen['interval'].split('s')[0])  # todo manage like it should
                should_be_launch = gen['last_launch'] < int(time.time()) - interval
                if should_be_launch:
                    logger.debug('Launching detector: %s rule: %s' % (gname, gen['apply_if']))
                    gen['last_launch'] = int(time.time())
                    try:
                        do_apply = evaluater.eval_expr(gen['apply_if'])
                    except Exception, exp:
                        logger.error('Cannot execute detector %s: %s' % (gname, exp))
                        do_apply = False
                    gen['do_apply'] = do_apply
                    if do_apply:
                        tags = gen['tags']
                        try:
                            # Try to evaluate the tag if need (can be an expression {} )
                            tags = [evaluater.compile(t) for t in tags]
                        except Exception, exp:
                            logger.error('Cannot execute detector tag %s: %s' % (gname, exp))
                            tags = []
                        logger.debug('Tags %s are applying for the detector %s' % (tags, gname))
                        self.detected_tags[gname] = tags
                    else:
                        self.detected_tags[gname] = []
            # take all from the current state of all detectors, and update gossiper about it
            for tags in self.detected_tags.values():
                for tag in tags:
                    matching_tags.add(tag)
            logger.debug('Detector loop generated tags: %s' % matching_tags, part='gossip')
            
            # Merge with gossip part
            did_changed = gossiper.update_detected_tags(matching_tags)
            # if tags did change, recompute checks
            if did_changed:
                monitoringmgr.link_checks()
            
            self.did_run = True  # ok we did detect our tags, we can be sure about us
            time.sleep(1)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        
        @http_export('/agent/detectors/')
        @http_export('/agent/detectors')
        def get_detectors():
            response.content_type = 'application/json'
            return json.dumps(self.clust.detectors.values())
        
        
        @http_export('/agent/detectors/run')
        @http_export('/agent/detectors/run/:dname')
        def _runrunrunr(dname=''):
            response.content_type = 'application/json'
            res = {}
            for (gname, gen) in self.clust.detectors.iteritems():
                if dname and dname != gname:
                    continue
                res[gname] = {'matched': False, 'tags': [], 'new_tags': []}
                logger.info("LAUNCHING DETECTOR: %s" % gen)
                try:
                    res[gname]['matched'] = evaluater.eval_expr(gen['apply_if'])
                except Exception, exp:
                    logger.error('Cannot execute detector %s: %s' % (gname, exp))
                    res[gname]['matched'] = False
                if res[gname]['matched']:
                    res[gname]['tags'] = gen['tags']
                    for tag in res[gname]['tags']:
                        if tag not in self.clust.tags:
                            res[gname]['new_tags'].append(tag)
                            logger.info("ADDING NEW TAGS: %s" % tag)
            
            return json.dumps(res)


detecter = DetectorMgr()
