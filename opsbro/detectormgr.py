import time
import json

from .log import LoggerFactory
from .stop import stopper
from .evaluater import evaluater
from .collectormanager import collectormgr
from .gossip import gossiper
from .monitoring import monitoringmgr
from .topic import topiker, TOPIC_AUTOMATIC_DECTECTION

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
        if 'if_group' not in detector:
            detector['if_group'] = detector['name']
        
        for prop in ['add_groups', 'apply_if']:
            if prop not in detector:
                logger.warning('Bad detector, missing property %s in the detector %s' % (prop, gname))
                return
        if not isinstance(detector['add_groups'], list):
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
    
    
    def _launch_detectors(self):
        matching_groups = set()
        for (gname, gen) in self.detectors.items():
            interval = int(gen['interval'].split('s')[0])  # todo manage like it should
            should_be_launch = gen['last_launch'] < int(time.time()) - interval
            if should_be_launch:
                logger.debug('Launching detector: %s rule: %s' % (gname, gen['apply_if']))
                gen['last_launch'] = int(time.time())
                try:
                    apply_if_expr = gen['apply_if']
                    do_apply = evaluater.eval_expr(apply_if_expr)
                except Exception as exp:
                    logger.error('Cannot execute detector %s apply_if rule "%s": %s' % (gname, apply_if_expr, exp))
                    do_apply = False
                gen['do_apply'] = do_apply
                if do_apply:
                    groups = gen['add_groups']
                    new_groups = []
                    try:
                        # Try to evaluate the group if need (can be an expression {} )
                        # NOTE: to_string=True to not have a json object with 'value' but directly the string value
                        for t in groups:
                            compile_group = evaluater.compile(t, to_string=True)
                            if ',' in compile_group:
                                for sub_compile_group in [_g.strip() for _g in compile_group.split(',')]:
                                    new_groups.append(sub_compile_group)
                            else:
                                new_groups.append(compile_group)
                        groups = new_groups
                    except Exception as exp:
                        logger.error('Cannot execute detector group %s: "%s" %s' % (gname, t, exp))
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
    
    
    # Main thread for launching detectors
    def do_detector_thread(self):
        # if the collector manager did not run, our evaluation can be invalid, so wait for all collectors to run at least once
        while collectormgr.did_run == False:
            time.sleep(0.25)
        # Ok we can use collector data :)
        logger.log('DETECTOR thread launched')
        while not stopper.is_stop():
            # Only launch detectors if we are allowed to
            if topiker.is_topic_enabled(TOPIC_AUTOMATIC_DECTECTION):
                self._launch_detectors()
            
            self.did_run = True  # ok we did detect our groups, we can be sure about us
            time.sleep(1)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        from .httpdaemon import http_export, response
        
        @http_export('/agent/detectors/')
        @http_export('/agent/detectors')
        def get_detectors():
            response.content_type = 'application/json'
            return json.dumps(self.detectors.values())
        
        
        @http_export('/agent/detectors/state')
        @http_export('/agent/detectors/state/')
        def get_detectors_state():
            response.content_type = 'application/json'
            return json.dumps(list(gossiper.detected_groups))
        
        
        @http_export('/agent/detectors/history', method='GET')
        def get_compliance_history():
            response.content_type = 'application/json'
            r = gossiper.get_history()
            return json.dumps(r)
        
        
        @http_export('/agent/detectors/run')
        @http_export('/agent/detectors/run/:dname')
        def _runrunrunr(dname=''):
            response.content_type = 'application/json'
            res = {}
            for (gname, gen) in self.detectors.items():
                if dname and dname != gname:
                    continue
                res[gname] = {'matched': False, 'groups': [], 'new_groups': []}
                logger.info("LAUNCHING DETECTOR: %s" % gen)
                try:
                    res[gname]['matched'] = evaluater.eval_expr(gen['apply_if'])
                except Exception as exp:
                    logger.error('Cannot execute detector %s: %s' % (gname, exp))
                    res[gname]['matched'] = False
                if res[gname]['matched']:
                    res[gname]['groups'] = gen['add_groups']
                    for group in res[gname]['groups']:
                        if group not in gossiper.groups:
                            res[gname]['new_groups'].append(group)
                            logger.info("ADDING NEW groupS: %s" % group)
            
            return json.dumps(res)


detecter = DetectorMgr()
