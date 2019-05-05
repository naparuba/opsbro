from __future__ import print_function
import re
import socket
import copy
import sys

PY3 = sys.version_info >= (3,)
if PY3:
    def byte_to_int(byte):  # already byte
        return byte
else:  # Python 2
    def byte_to_int(byte):
        return ord(byte)

from opsbro.gossip import gossiper
from opsbro.util import bytes_to_unicode, unicode_to_bytes

pattern = r"((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)([ (\[]?(\.|dot)[ )\]]?(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3})"
ipv4pattern = re.compile(pattern)


class DNSQuery:
    # Global logger will be set by the module
    logger = None
    
    
    def __init__(self, data):
        self.data = data
        self.domain = ''
        
        t = (byte_to_int(data[2]) >> 3) & 15  # Opcode bits
        if t == 0:  # Standard query
            ini = 12
            lon = byte_to_int(data[ini])
            while lon != 0:
                self.domain += bytes_to_unicode(data[ini + 1: ini + lon + 1]) + '.'
                ini += lon + 1
                lon = byte_to_int(data[ini])
    
    
    @staticmethod
    def _get_size_hex(nb):
        nb = min(nb, 256 * 256)
        d, r = divmod(nb, 256)
        s = chr(d) + chr(r)
        return unicode_to_bytes(s)
    
    
    @staticmethod
    def _int_to_byte(n):
        if PY3:
            return bytes([int(n)])
        else:
            return chr(int(n))
    
    
    # TODO: add a cache
    def _get_node_ip(self, node):
        addr = node['public_addr']
        # If already an ip, add it
        if ipv4pattern.match(addr):
            return addr
        
        # else try to resolv it first
        try:
            addr = socket.gethostbyname(addr)
            return addr
        except socket.gaierror:  # not found
            self.logger.debug('DNS cannot find the hostname ip %s' % addr)
            return None
    
    
    # We look in the nodes for the good group
    def lookup_for_nodes(self, dom):
        self.logger.debug('Querying %s for managed domaine: %s' % (dom, self.domain))
        if not self.domain.endswith(dom):
            self.logger.debug('Domain %s is not matching managed domain: %s' % (dom, self.domain))
            return []
        search = self.domain[:-len(dom)]
        # split into sname.service.datacenter
        self.logger.debug("Lookup for search %s" % search)
        elts = search.split('.', 2)
        if len(elts) != 3:
            self.logger.error('Bad query, not 3 dots in %s' % search)
            return []
        # NOTE: zone is currently ignored
        zone = elts[2]
        # Filter type must be in 2:
        # - group => look for a group
        # - name  => look for a name (or a display name)
        filter_type = elts[1]
        filter_value = elts[0]
        if filter_type not in ('group', 'name'):
            self.logger.error('This module do not manage this DNS query type: %s' % filter_type)
            return []
        
        self.logger.debug('Looking in %s nodes' % len(gossiper.nodes))
        r = []
        
        if filter_type == 'group':
            group = filter_value
            valid_filter_node_uuids = gossiper.find_group_nodes(group)
        
        else:  # filter by name
            name = filter_value
            valid_filter_node_uuids = gossiper.find_nodes_by_name_or_display_name(name)
        
        # Now look for real node & addr/ip
        for node_uuid in valid_filter_node_uuids:
            node = gossiper.get(node_uuid)
            if node is None:  # magic thread disapearance
                continue
            addr = self._get_node_ip(node)
            if addr is not None:
                r.append(addr)
        self.logger.debug('DNS return %s' % r)
        return r
    
    
    # Get origianl question from DATA, and only this, so stip to NAME+0001(typeA)+0001(IN) and drop what is after
    @staticmethod
    def __get_original_domain_name_question(data):
        # first find the end of the string, with \x00
        end_string_idx = data.find(b'\x00')
        if end_string_idx == -1:
            # ok bad query, fuck off
            return data
        # so give 2bytes after the end
        return data[:end_string_idx + 5]  # 5=1 for \00 and 2+2 for typeA+IN
    
    
    def response(self, r):
        packet = b''
        # r = ['192.168.56.103', '192.168.56.104' , '192.168.56.105']
        nb = len(r)
        if self.domain:
            packet += self.data[:2] + b'\x81\x80'
            packet += self.data[4:6] + self._get_size_hex(nb) + b'\x00\x00\x00\x00'  # Questions and Answers Counts, and additionnal counts (0)
            packet += self.__get_original_domain_name_question(self.data[12:])  # Original Domain Name Question, split to remove additonna parts
            
            for ip in r:
                packet += b'\xc0\x0c'  # Pointer to domain name
                packet += b'\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'  # Response type, ttl (60s) and resource data length -> 4 bytes
                for n in ip.split('.'):
                    packet += self._int_to_byte(n)
        
        self.logger.debug("Returning size: %s for nb ips:%s" % (len(packet), len(r)))
        return packet
