import socket
import time
import traceback

from opsbro.threadmgr import threader
from opsbro.module import Module
from opsbro.stop import stopper
from opsbro.parameters import StringParameter, IntParameter
from opsbro.detectormgr import detecter
from opsbro.gossip import gossiper

from dnsquery import DNSQuery


class DNSModule(Module):
    implement = 'dns'
    
    parameters = {
        'enabled_if_group': StringParameter(default='dns-listener'),
        'port'            : IntParameter(default=6766),
        'domain'          : StringParameter(default='.opsbro'),
    }
    
    
    def __init__(self):
        super(DNSModule, self).__init__()
        self.enabled = False
        self.port = 0
        self.domain = ''
        self.sock = None
        
        # Let my logger to the sub class
        DNSQuery.logger = self.logger
    
    
    def get_my_parameters(self):
        if_group = self.get_parameter('enabled_if_group')
        enabled = gossiper.is_in_group(if_group)
        self.logger.debug('Looking if the group %s is matching: %s' % (if_group, enabled))
        port = self.get_parameter('port')
        domain = self.get_parameter('domain')
        # assume that domain is like .foo.
        if not domain.endswith('.'):
            domain += '.'
        if not domain.startswith('.'):
            domain = '.' + domain
        return enabled, port, domain
    
    
    def get_info(self):
        state = 'STARTED' if self.enabled else 'DISABLED'
        log = ''
        return {'configuration': self.get_config(), 'state': state, 'log': log}

    
    
    def launch(self):
        threader.create_and_launch(self.do_launch, name='UDP port:%d listening' % self.port, essential=True, part='dns')
    
    
    def close_socket(self):
        if self.sock is None:
            return
        try:
            self.sock.close()
        except Exception, exp:
            self.logger.error('Cannot close DNS socket: %s' % exp)
        self.sock = None
    
    
    def bind(self):
        # Always be sure to close our socket if binding a new
        self.close_socket()
        self.logger.info('Opening UDP port')
        # Prepare the socket in the prepare phase because it's mandatory
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.logger.info('DNS launched server port %d' % self.port)
        try:
            self.sock.bind(('', self.port))
        except Exception, exp:
            self.logger.error('Cannot open the DNS port %s : %s' % (self.port, exp))
            self.sock = None
    
    
    def do_launch(self):
        # If the detector did not run, we are not sure about the groups of the local node
        # so wait for it to be run
        while not detecter.did_run:
            time.sleep(1)
        
        while not stopper.interrupted:
            # Note: domain is dynamic in analysis, don't need to look at differences
            was_enabled, prev_port = self.enabled, self.port
            self.enabled, self.port, self.domain = self.get_my_parameters()
            
            # Manage stop or skip loop
            if not self.enabled:
                # If we are going to stop, close our socket and wait for new enabled
                if was_enabled:
                    self.close_socket()
                # Ok wait a bit
                time.sleep(1)
                continue
            
            # Multiple cases will need us to open/reopen the socket
            # but we want to do it only once
            reopen = False
            
            # We are enabled, maybe we were not just before
            # if so we must bind our port
            if not was_enabled:
                reopen = True
            
            # Maybe just the port did change
            if self.port != prev_port:
                reopen = True
            
            # Maybe we fail to open it before (port already open ?)
            if self.sock is None:
                reopen = True
            
            # Ok if we need to reopen, do it
            if reopen:
                self.bind()
            
            # But maybe we did miss the bind
            # so skip this turn
            if self.sock is None:
                time.sleep(1)
                continue
            
            # Ok we are good :)
            try:
                data, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue  # loop until we got some data :)
            
            try:
                p = DNSQuery(data)
                r = p.lookup_for_nodes(self.domain)
                self.logger.debug("DNS lookup nodes response:", r)
                self.sock.sendto(p.response(r), addr)
            except Exception:
                self.logger.error('Module got issue: %s' % (str(traceback.format_exc())))
