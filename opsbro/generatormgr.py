import time
import os
import json

from .log import LoggerFactory
from .stop import stopper
from .generator import Generator, GENERATOR_STATES
from .httpdaemon import http_export, response
from .basemanager import BaseManager

# Global logger for this part
logger = LoggerFactory.create_logger('generator')


class GeneratorMgr(BaseManager):
    history_directory_suffix = 'generator'
    
    
    def __init__(self):
        super(GeneratorMgr, self).__init__()
        
        self.logger = logger
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
        
        generator['generate_if'] = generator.get('generate_if', 'False')
        
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
        # Before run, be sure we have a history directory ready
        self.prepare_history_directory()
        
        logger.log('GENERATOR thread launched')
        while not stopper.interrupted:
            logger.debug('Looking for %d generators' % len(self.generators))
            for (gname, g) in self.generators.items():
                logger.debug('LOOK AT GENERATOR', g, 'to be apply if', g.generate_if)
                # Maybe this generator is not for us...
                if not g.must_be_launched():
                    continue
                logger.debug('Generator %s will generate' % str(g.__dict__))
                g.generate()
                logger.debug('Generator %s is generated' % str(g.__dict__))
                should_launch = g.write_if_need()
                if should_launch:
                    g.launch_command()
                history_entry = g.get_history_entry()
                if history_entry:
                    self.add_history_entry(history_entry)
            
            # Ok we did run at least once :)
            self.did_run = True
            
            # each seconds we try to look if there are history info to save
            self.write_history_entry()
            
            time.sleep(1)
    
    
    def get_infos(self):
        r = {}
        for state in GENERATOR_STATES:
            r[state] = 0
        for g in self.generators.values():
            r[g.get_state()] += 1
        return r
    
    
    def export_http(self):
        
        @http_export('/generators/history', method='GET')
        def get_generator_history_checks():
            response.content_type = 'application/json'
            r = self.get_history()
            return json.dumps(r)
        
        
        @http_export('/generators/state', method='GET')
        def get_generator_state():
            response.content_type = 'application/json'
            nc = {}
            for (c_id, c) in self.generators.items():
                nc[c_id] = c.get_json_dump()
            return json.dumps(nc)


generatormgr = GeneratorMgr()
