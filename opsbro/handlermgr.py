from .log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('handler')


class HandlerManager(object):
    def __init__(self):
        self.handler_modules = {}
    
    
    def register_handler_module(self, implement, module):
        self.handler_modules[implement] = module
    
    
    def launch_check_handlers(self, check, did_change):
        logger.debug('Launch handlers(check): %s (didchange=%s)' % (check['name'], did_change))
        
        for (htype, module) in self.handler_modules.items():
            module.handle(check, {'evt_type': 'check_execution', 'evt_data': {'check_did_change': did_change}})
    
    
    def launch_group_handlers(self, group, what):
        logger.debug('Launch handlers(group): %s (what=%s)' % (group, what))
        
        for (htype, module) in self.handler_modules.items():
            module.handle(group, {'evt_type': 'group_change', 'evt_data': {'modification': what}})


    def launch_compliance_handlers(self, compliance, did_change):
        logger.debug('Launch handlers(compliance): %s (didchange=%s)' % (compliance.get_name(), did_change))
        
        for (htype, module) in self.handler_modules.items():
            module.handle(compliance, {'evt_type': 'compliance_execution', 'evt_data': {'compliance_did_change': did_change}})


handlermgr = HandlerManager()
