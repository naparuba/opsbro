from .log import LoggerFactory, DEFAULT_LOG_PART

logger = LoggerFactory.create_logger(DEFAULT_LOG_PART)


class UDPRouting(object):
    def __init__(self):
        self.routes = {}
    
    
    def declare_handler(self, route_prefix, handler):
        self.routes[route_prefix] = handler
    
    
    def route_message(self, message, source_addr):
        _type = message.get('type', None)
        if _type is None:
            logger.error('We did received a UDP message without type')
            return
        if '::' not in _type:
            logger.error('We did received a UDP message but with invalid type: %s (not with ::)' % _type)
            return
        # we are safe to split now
        prefix, handler_part_type = _type.split('::')
        handler = self.routes.get(prefix, None)
        if handler is None:
            logger.error('We did received a valid UDP message but we do not have any handler for it: %s' % _type)
            return
        # We call the handler, and here, I prefer NOT to set try/except and have a real error
        # in the udp thread that make silent errors
        # TODO: make handler resilient, by them declaring to be try/except if need, like modules
        handler.manage_message(_type, message, source_addr)


# Global udp router object, that will read and route UDP message to handlers like gossiper or kvmgr
udprouter = UDPRouting()
