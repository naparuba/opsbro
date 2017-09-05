import os
import time

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('handler')


class HandlerManager(object):
    def __init__(self):
        self.handlers = {}
        self.handler_modules = {}
    
    
    def register_handler_module(self, implement, module):
        self.handler_modules[implement] = module
    
    
    def import_handler(self, handler, full_path, file_name, mod_time=0, pack_name='', pack_level=''):
        handler['from'] = full_path
        handler['pack_name'] = pack_name
        handler['pack_level'] = pack_level
        handler['configuration_dir'] = os.path.dirname(full_path)
        handler['name'] = handler['id']
        if 'notes' not in handler:
            handler['notes'] = ''
        handler['modification_time'] = mod_time
        # look at types now
        if 'type' not in handler:
            handler['type'] = 'none'
        _type = handler['type']

        if _type == 'slack':
            handler['slack_token'] = handler.get('slack_token', os.environ.get('SLACK_TOKEN', ''))
            handler['channel'] = handler.get('channel', '#general')
        
        # Add it into the list
        self.handlers[handler['id']] = handler
    
    
    def launch_check_handlers(self, check, did_change):
        logger.debug('Launch handlers: %s (didchange=%s)' % (check['name'], did_change))
        
        for (hname, handler) in self.handlers.iteritems():
            htype = handler['type']
            logger.info('LAUNCH HANDLERS BASED ON %s/%s' % (htype, self.handler_modules))
            if htype in self.handler_modules:
                module = self.handler_modules[htype]
                module.handle(handler, check, {'evt_type': 'check_execution', 'evt_data': {'check_did_change': did_change}})
            else:
                logger.do_warning('The handler type %s is not managed by a module' % htype)


handlermgr = HandlerManager()
