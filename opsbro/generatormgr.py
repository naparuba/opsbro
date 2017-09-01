import time
import os

from opsbro.log import LoggerFactory
from opsbro.stop import stopper
from opsbro.httpdaemon import http_export, response
from opsbro.evaluater import evaluater
from opsbro.collectormanager import collectormgr
from opsbro.gossip import gossiper
from opsbro.monitoring import monitoringmgr
from opsbro.generator import Generator

# Global logger for this part
logger = LoggerFactory.create_logger('generator')


class GeneratorMgr(object):
    def __init__(self):
        self.generators = {}
    
    
    # Generators will create files based on templates from
    # data and nodes after a change on a node
    def import_generator(self, generator, fr, gname, mod_time=0, pack_name='', pack_level=''):
        generator['from'] = fr
        generator['pack_name'] = pack_name
        generator['pack_level'] = pack_level
        generator['name'] = generator['id'] = gname
        if 'notes' not in generator:
            generator['notes'] = ''
        if 'apply_on' not in generator:
            generator['apply_on'] = generator['name']
        
        for prop in ['path', 'template']:
            if prop not in generator:
                logger.warning('Bad generator, missing property %s in the generator %s' % (prop, gname))
                return
        # Template must be from configuration path
        gen_base_dir = os.path.dirname(fr)
        
        generator['template'] = os.path.normpath(os.path.join(gen_base_dir, generator['template']))
        # and path must be a abs path
        generator['path'] = os.path.abspath(generator['path'])
        
        # We will try not to hummer the generator
        generator['modification_time'] = mod_time
        
        for k in ['partial_start', 'partial_end']:
            if k not in generator:
                generator[k] = ''
        
        generator['if_partial_missing'] = generator.get('if_partial_missing', '')
        if generator['if_partial_missing'] and generator['if_partial_missing'] not in ['append']:
            logger.error('Generator %s if_partial_missing property is not valid: %s' % (generator['name'], generator['if_partial_missing']))
            return
        
        # Add it into the generators list
        self.generators[generator['id']] = generator
    
    
    # Main thread for launching generators
    def do_generator_thread(self):
        logger.log('GENERATOR thread launched')
        while not stopper.interrupted:
            logger.debug('Looking for %d generators' % len(self.generators))
            for (gname, gen) in self.generators.iteritems():
                logger.debug('LOOK AT GENERATOR', gen, 'to be apply on', gen['apply_on'], 'with our groups', gossiper.groups)
                apply_on = gen['apply_on']
                # Maybe this generator is not for us...
                if apply_on != '*' and apply_on not in gossiper.groups:
                    continue
                logger.debug('Generator %s will runs' % gname)
                g = Generator(gen)
                logger.debug('Generator %s will generate' % str(g.__dict__))
                g.generate()
                logger.debug('Generator %s is generated' % str(g.__dict__))
                should_launch = g.write_if_need()
                if should_launch:
                    g.launch_command()
            time.sleep(1)


generatormgr = GeneratorMgr()
