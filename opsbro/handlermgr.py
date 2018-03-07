from .log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('handler')


class HandlerManager(object):
    def __init__(self):
        self.handler_modules = {}
    
    
    def register_handler_module(self, implement, module):
        self.handler_modules[implement] = module
    
    
    def launch_check_handlers(self, check, did_change):
        logger.debug('Launch handlers: %s (didchange=%s)' % (check['name'], did_change))
        
        for (htype, module) in self.handler_modules.iteritems():
            module.handle(check, {'evt_type': 'check_execution', 'evt_data': {'check_did_change': did_change}})


handlermgr = HandlerManager()
