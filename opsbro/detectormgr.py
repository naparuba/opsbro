import time
import json

from opsbro.log import LoggerFactory
from opsbro.stop import stopper
from opsbro.httpdaemon import http_export, response
from opsbro.evaluater import evaluater
from opsbro.collectormanager import collectormgr
from opsbro.gossip import gossiper
from opsbro.monitoring import monitoringmgr

# Global logger for this part
logger = LoggerFactory.create_logger('detector')


class DetectorMgr(object):
    def __init__(self):
        self.did_run = False  # did we run at least once? so are our groups ok currently?
        self.detected_groups = {}
        self.detectors = {}
    
    
    # Detectors will run rules based on collectors and such things, and will group the local node
    # if the rules are matching
    def import_detector(self, detector, fr, gname, mod_time=0, pack_name='', pack_level=''):
        detector['from'] = fr
        detector['pack_name'] = pack_name
        detector['pack_level'] = pack_level
        detector['name'] = detector['id'] = gname
        if 'notes' not in detector:
            detector['notes'] = ''
        if 'apply_on' not in detector:
            detector['apply_on'] = detector['name']
        
        for prop in ['groups', 'apply_if']:
            if prop not in detector:
                logger.warning('Bad detector, missing property %s in the detector %s' % (prop, gname))
                return
        if not isinstance(detector['groups'], list):
            logger.warning('Bad detector, groups is not a list in the detector %s' % gname)
            return
        
        # We will try not to hummer the detector
        detector['modification_time'] = mod_time
        
        # Do not lunach too much
        detector['last_launch'] = 0
        
        # By default do not match
        detector['do_apply'] = False
        
        # Add it into the detectors list
        self.detectors[detector['id']] = detector
    
    
    # Main thread for launching detectors
    def do_detector_thread(self):
        # if the collector manager did not run, our evaluation can be invalid, so wait for all collectors to run at least once
        while collectormgr.did_run == False:
            time.sleep(1)
        # Ok we can use collector data :)
        logger.log('DETECTOR thread launched')
        while not stopper.interrupted:
            matching_groups = set()
            for (gname, gen) in self.detectors.iteritems():
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
                        groups = gen['groups']
                        try:
                            # Try to evaluate the group if need (can be an expression {} )
                            # NOTE: to_string=True to not have a json object with 'value' but directly the string value
                            groups = [evaluater.compile(t, to_string=True) for t in groups]
                        except Exception, exp:
                            logger.error('Cannot execute detector group %s: %s' % (gname, exp))
                            groups = []
                        logger.debug('groups %s are applying for the detector %s' % (groups, gname))
                        self.detected_groups[gname] = groups
                    else:
                        self.detected_groups[gname] = []
            # take all from the current state of all detectors, and update gossiper about it
            for groups in self.detected_groups.values():
                for group in groups:
                    matching_groups.add(group)
            logger.debug('Detector loop generated groups: %s' % matching_groups, part='gossip')
            
            # Merge with gossip part
            did_changed = gossiper.update_detected_groups(matching_groups)
            # if groups did change, recompute checks
            if did_changed:
                monitoringmgr.link_checks()
            
            self.did_run = True  # ok we did detect our groups, we can be sure about us
            time.sleep(1)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        
        @http_export('/agent/detectors/')
        @http_export('/agent/detectors')
        def get_detectors():
            response.content_type = 'application/json'
            return json.dumps(self.detectors.values())
        
        
        @http_export('/agent/detectors/run')
        @http_export('/agent/detectors/run/:dname')
        def _runrunrunr(dname=''):
            response.content_type = 'application/json'
            res = {}
            for (gname, gen) in self.detectors.iteritems():
                if dname and dname != gname:
                    continue
                res[gname] = {'matched': False, 'groups': [], 'new_groups': []}
                logger.info("LAUNCHING DETECTOR: %s" % gen)
                try:
                    res[gname]['matched'] = evaluater.eval_expr(gen['apply_if'])
                except Exception, exp:
                    logger.error('Cannot execute detector %s: %s' % (gname, exp))
                    res[gname]['matched'] = False
                if res[gname]['matched']:
                    res[gname]['groups'] = gen['groups']
                    for group in res[gname]['groups']:
                        if group not in gossiper.groups:
                            res[gname]['new_groups'].append(group)
                            logger.info("ADDING NEW groupS: %s" % group)
            
            return json.dumps(res)


detecter = DetectorMgr()
