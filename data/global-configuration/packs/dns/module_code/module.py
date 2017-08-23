import socket

from opsbro.log import LoggerFactory
from opsbro.threadmgr import threader
from opsbro.module import Module
from opsbro.stop import stopper
from opsbro.parameters import StringParameter, BoolParameter, IntParameter

from dnsquery import DNSQuery

# Global logger for this part
logger = LoggerFactory.create_logger('dns')


class DNSModule(Module):
    implement = 'dns'
    manage_configuration_objects = ['dns']
    parameters = {
        'enabled': BoolParameter(default=False),
        'port'   : IntParameter(default=53),
        'domain' : StringParameter(default=''),
    }
    
    
    def __init__(self):
        Module.__init__(self)
        self.dns = None
        self.enabled = False
        self.port = 0
        self.domain = ''
        self.sock = None
    
    
    def import_configuration_object(self, object_type, o, mod_time, fname, short_name):
        self.dns = o
    
    
    # Prepare to open the UDP port
    def prepare(self):
        logger.debug('DNS: prepare phase')
        if self.dns:
            self.enabled = self.dns.get('enabled', False)
            self.port = self.dns.get('port', 53)
            self.domain = self.dns.get('domain', '')
            # assume that domain is like .foo.
            if not self.domain.endswith('.'):
                self.domain += '.'
            if not self.domain.startswith('.'):
                self.domain = '.' + self.domain
            if self.enabled:
                logger.info('DNS is enabled, opening UDP port')
                # Prepare the socket in the prepare phase because it's mandatory
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                logger.info('DNS launched server port %d' % self.port)
                self.sock.bind(('', self.port))
            else:
                logger.info('DNS is not enabled, skipping it')
    
    
    def get_info(self):
        return {'dns_configuration': self.dns, 'dns_info': None}
    
    
    def launch(self):
        threader.create_and_launch(self.do_launch, name='UDP port:%d listening' % self.port, essential=True, part='dns')
    
    
    def do_launch(self):
        if not self.enabled:
            logger.error('No dns object defined in the configuration or not enabled, skipping it')
            return
        
        while not stopper.interrupted:
            logger.debug('DNS MODULE LOOP')
            try:
                data, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue  # loop until we got some data :)
            
            try:
                p = DNSQuery(data)
                r = p.lookup_for_nodes(self.domain)
                logger.debug("DNS lookup nodes response:", r)
                self.sock.sendto(p.response(r), addr)
            except Exception, exp:
                logger.log("DNS problem", exp)
