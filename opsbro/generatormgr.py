import time
import os

from .log import LoggerFactory
from .stop import stopper
from .generator import Generator, GENERATOR_STATES

# Global logger for this part
logger = LoggerFactory.create_logger('generator')


class GeneratorMgr(object):
    def __init__(self):
        self.generators = {}
        # Did we run at least once
        self.did_run = False
    
    
    # Generators will create files based on templates from
    # data and nodes after a change on a node
    def import_generator(self, generator, fr, gname, mod_time=0, pack_name='', pack_level=''):
        generator['from'] = fr
        generator['pack_name'] = pack_name
        generator['pack_level'] = pack_level
        generator['name'] = generator['id'] = gname
        if 'notes' not in generator:
            generator['notes'] = ''
        if 'if_group' not in generator:
            generator['if_group'] = generator['name']
        
        for prop in ['path', 'template']:
            if prop not in generator:
                logger.warning('Bad generator, missing property %s in the generator %s' % (prop, gname))
                return
        # Template must be from configuration path
        gen_base_dir = os.path.dirname(fr)
        
        generator['template'] = os.path.normpath(os.path.join(gen_base_dir, 'templates', generator['template']))
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
        self.generators[generator['id']] = Generator(generator)
    
    
    # Main thread for launching generators
    def do_generator_thread(self):
        logger.log('GENERATOR thread launched')
        while not stopper.interrupted:
            logger.debug('Looking for %d generators' % len(self.generators))
            for (gname, g) in self.generators.iteritems():
                logger.debug('LOOK AT GENERATOR', g, 'to be apply on', g.if_group)
                # Maybe this generator is not for us...
                if not g.must_be_launched():
                    continue
                logger.debug('Generator %s will generate' % str(g.__dict__))
                g.generate()
                logger.debug('Generator %s is generated' % str(g.__dict__))
                should_launch = g.write_if_need()
                if should_launch:
                    g.launch_command()
            # Ok we did run at least once :)
            self.did_run = True
            time.sleep(1)
    
    
    def get_infos(self):
        r = {}
        for state in GENERATOR_STATES:
            r[state] = 0
        for g in self.generators.values():
            r[g.state] += 1
        return r


generatormgr = GeneratorMgr()
