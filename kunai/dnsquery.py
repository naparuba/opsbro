import re
import socket

from kunai.log import logger

pattern = r"((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)([ (\[]?(\.|dot)[ )\]]?(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3})"
ipv4pattern = re.compile(pattern)


class DNSQuery:
    def __init__(self, data):
        self.data = data
        self.domain = ''
        
        t = (ord(data[2]) >> 3) & 15  # Opcode bits
        if t == 0:  # Standard query
            ini = 12
            lon = ord(data[ini])
            while lon != 0:
                self.domain += data[ini + 1: ini + lon + 1] + '.'
                ini += lon + 1
                lon = ord(data[ini])
    
    
    def _get_size_hex(self, nb):
        nb = min(nb, 256 * 256)
        d, r = divmod(nb, 256)
        s = chr(d) + chr(r)
        return s
    
    
    # We look in the nodes for the good tag
    def lookup_for_nodes(self, nodes, dom):
        logger.debug('Querying %s for managed domaine: %s' % (dom, self.domain), part='dns')
        if not self.domain.endswith(dom):
            logger.debug('Domain %s is not matching managed domain: %s' % (dom, self.domain), part='dns')
            return []
        search = self.domain[:-len(dom)]
        # split into sname.service.datacenter
        logger.debug("Lookup for search %s" % search, part='dns')
        elts = search.split('.', 2)
        if len(elts) != 3:
            logger.debug('Bad query, not 3 dots in %s' % search, part='dns')
            return []
        dc = elts[2]
        _type = elts[1]
        tag = elts[0]
        logger.debug('Looking in %s nodes' % len(nodes), part='dns')
        r = []
        for n in nodes.values():
            # skip non alive nodes
            if n['state'] != 'alive':
                logger.debug('Skipping node %s, state=%s != alive' % (n['name'], n['state']))
                continue
            if tag in n['tags']:
                services = n.get('services', {})
                state_id = 0
                if tag in services:
                    service = services[tag]
                    state_id = service.get('state_id')
                logger.debug('current state id : %s' % state_id, part='dns')
                # Skip bad nodes
                if state_id != 0:
                    logger.debug('Skipping node %s' % n['name'])
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
                        print 'DNS cannot find the hotname ip', addr
                        # skip this node
        
        logger.debug('DNS return %s' % r)
        return r
    
    # Get origianl question from DATA, and only this, so stip to NAME+0001(typeA)+0001(IN) and drop what is after
    def __get_origianl_domain_name_question(self, data):
        # first find the end of the string, with \x00
        end_string_idx = data.find('\x00')
        if end_string_idx == -1:
            # ok bad query, fuck off
            return data
        # so give 2bytes after the end
        return data[:end_string_idx+5]  # 5=1 for \00 and 2+2 for typeA+IN
    
    
    def response(self, r):
        packet = ''
        #r = ['192.168.56.103', '192.168.56.104' , '192.168.56.105']
        nb = len(r)
        if self.domain:
            packet += self.data[:2] + "\x81\x80"
            packet += self.data[4:6] + self._get_size_hex(nb)  + '\x00\x00\x00\x00'  # Questions and Answers Counts, and additionnal counts (0)
            packet += self.__get_origianl_domain_name_question(self.data[12:])  # Original Domain Name Question, split to remove additonna parts
            
            for ip in r:
                packet += '\xc0\x0c'  # Pointer to domain name
                packet += '\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'  # Response type, ttl (60s) and resource data length -> 4 bytes
                packet += str.join('', map(lambda x: chr(int(x)), ip.split('.')))  # 4bytes of IP


        logger.debug("Returning size: %s for nb ips:%s" % (len(packet), len(r)))
        return packet
