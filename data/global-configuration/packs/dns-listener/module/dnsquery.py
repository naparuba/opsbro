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
    
    
    def _get_size_hex(self, nb):
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
    
    
    # We look in the nodes for the good group
    def lookup_for_nodes(self, dom):
        # TODO: copy nodes can be huge, maybe ask gossip to have a static list?
        with gossiper.nodes_lock:
            nodes = copy.copy(gossiper.nodes)
        self.logger.debug('Querying %s for managed domaine: %s' % (dom, self.domain))
        if not self.domain.endswith(dom):
            self.logger.debug('Domain %s is not matching managed domain: %s' % (dom, self.domain))
            return []
        search = self.domain[:-len(dom)]
        # split into sname.service.datacenter
        self.logger.debug("Lookup for search %s" % search)
        elts = search.split('.', 2)
        if len(elts) != 3:
            self.logger.debug('Bad query, not 3 dots in %s' % search)
            return []
        dc = elts[2]
        _type = elts[1]
        group = elts[0]
        self.logger.debug('Looking in %s nodes' % len(nodes))
        r = []
        for n in nodes.values():
            # skip non alive nodes
            if n['state'] != 'alive':
                self.logger.debug('Skipping node %s, state=%s != alive' % (n['name'], n['state']))
                continue
            if group in n['groups']:
                services = n.get('services', {})
                state_id = 0
                if group in services:
                    service = services[group]
                    state_id = service.get('state_id')
                self.logger.debug('current state id : %s' % state_id)
                # Skip bad nodes
                if state_id != 0:
                    self.logger.debug('Skipping node %s' % n['name'])
                    continue
                
                addr = n['addr']
                # If already an ip, add it
                if ipv4pattern.match(addr):
                    r.append(addr)
                else:  # else try to resolv it first
                    try:
                        addr = socket.gethostbyname(addr)
                        r.append(addr)
                    except socket.gaierror:  # not found
                        print('DNS cannot find the hotname ip', addr)
                        # skip this node
        
        self.logger.debug('DNS return %s' % r)
        return r
    
    
    # Get origianl question from DATA, and only this, so stip to NAME+0001(typeA)+0001(IN) and drop what is after
    def __get_origianl_domain_name_question(self, data):
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
            packet += self.__get_origianl_domain_name_question(self.data[12:])  # Original Domain Name Question, split to remove additonna parts
            
            for ip in r:
                packet += b'\xc0\x0c'  # Pointer to domain name
                packet += b'\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'  # Response type, ttl (60s) and resource data length -> 4 bytes
                for n in ip.split('.'):
                    packet += self._int_to_byte(n)
        
        self.logger.debug("Returning size: %s for nb ips:%s" % (len(packet), len(r)))
        # if not PY3:
        #    self.logger.debug(":".join("{:02x}".format(ord(c)) for c in packet))
        # else:
        #    self.logger.debug(":".join("{:02x}".format(c) for c in packet))
        return packet
