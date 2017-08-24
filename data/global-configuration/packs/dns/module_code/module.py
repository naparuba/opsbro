import socket

from opsbro.threadmgr import threader
from opsbro.module import Module
from opsbro.stop import stopper
from opsbro.parameters import StringParameter, BoolParameter, IntParameter

from dnsquery import DNSQuery


class DNSModule(Module):
    implement = 'dns'
    
    parameters = {
        'enabled': BoolParameter(default=False),
        'port'   : IntParameter(default=53),
        'domain' : StringParameter(default=''),
    }
    
    
    def __init__(self):
        Module.__init__(self)
        self.enabled = False
        self.port = 0
        self.domain = ''
        self.sock = None
        
        # Let my logger to the sub class
        DNSQuery.logger = self.logger
    
    
    # Prepare to open the UDP port
    def prepare(self):
        self.logger.debug('DNS: prepare phase')
        self.enabled = self.get_parameter('enabled')
        self.port = self.get_parameter('port')
        self.domain = self.get_parameter('domain')
        # assume that domain is like .foo.
        if not self.domain.endswith('.'):
            self.domain += '.'
        if not self.domain.startswith('.'):
            self.domain = '.' + self.domain
        if self.enabled:
            self.logger.info('DNS is enabled, opening UDP port')
            # Prepare the socket in the prepare phase because it's mandatory
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.logger.info('DNS launched server port %d' % self.port)
            self.sock.bind(('', self.port))
        else:
            self.logger.info('DNS is not enabled, skipping it')
    
    
    def get_info(self):
        return {'dns_configuration': self.get_config(), 'dns_info': None}
    
    
    def launch(self):
        threader.create_and_launch(self.do_launch, name='UDP port:%d listening' % self.port, essential=True, part='dns')
    
    
    def do_launch(self):
        if not self.enabled:
            self.logger.error('No dns object defined in the configuration or not enabled, skipping it')
            return
        
        while not stopper.interrupted:
            self.logger.debug('DNS MODULE LOOP')
            try:
                data, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue  # loop until we got some data :)
            
            try:
                p = DNSQuery(data)
                r = p.lookup_for_nodes(self.domain)
                self.logger.debug("DNS lookup nodes response:", r)
                self.sock.sendto(p.response(r), addr)
            except Exception, exp:
                self.logger.log("DNS problem", exp)
