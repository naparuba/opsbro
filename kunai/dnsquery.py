import re
import socket



pattern = r"((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)([ (\[]?(\.|dot)[ )\]]?(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3})"
ipv4pattern = re.compile(pattern)

class DNSQuery:
   def __init__(self, data):
      self.data = data
      self.domain = ''
      
      t = (ord(data[2]) >> 3) & 15   # Opcode bits
      if t == 0:                     # Standard query
         ini = 12
         lon = ord(data[ini])
         while lon != 0:
            self.domain += data[ini+1:ini+lon+1]+'.'
            ini += lon+1
            lon = ord(data[ini])

      
   def _get_size_hex(self, nb):
      nb = min(nb, 256*256)
      d,r = divmod(nb, 256)
      s = chr(d)+chr(r)
      return s

    
   # We look in the nodes for the good tag
   def lookup_for_nodes(self, nodes, dom):
      print "DNS LOOKING ", self.domain, "inside domain", dom
      if not self.domain.endswith(dom):
          return []
      search = self.domain[:-len(dom)]
      # split into sname.service.datacenter
      print "DNS lookup for search", search
      elts = search.split('.', 2)
      if len(elts) != 3:
         print "DNS bad query", search
         return []
      dc = elts[2]
      _type = elts[1]
      tag = elts[0]
      r = []
      for n in nodes.values():
         # skip non alive nodes
         if n['state'] != 'alive':
            continue
         if tag in n['tags']:
            services = n.get('services', {})
            state_id = 0
            if tag in services:
               service = services[tag]
               state_id = service.get('state_id')
            print "DNS state_id", state_id
            if state_id == 0:
               addr = n['addr']
               # If already an ip, add it
               if ipv4pattern.match(addr):
                  r.append(addr)
               else: # else try to resolv it first
                  try:
                     addr = socket.gethostbyname(addr)
                     r.append(addr)
                  except socket.gaierror: # not found
                     print 'DNS cannot find the hotname ip', addr
                     # skip this node
      
      print "DNS R:", r
      return r


   def response(self, r):
      packet = ''
      print "DNS DOM", self.domain
      nb = len(r)
      if self.domain:
         packet += self.data[:2] + "\x81\x80"
         packet += self.data[4:6] + self._get_size_hex(nb) + '\x00\x00\x00\x00'   # Questions and Answers Counts
         packet += self.data[12:]                                         # Original Domain Name Question

         for ip in r:
            packet += '\xc0\x0c'                                 # Pointer to domain name
            packet += '\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04' # Response type, ttl and resource data length -> 4 bytes
            packet += str.join('',map(lambda x: chr(int(x)), ip.split('.'))) # 4bytes of IP
      
      print "DNS RETURNing", len(packet), len(r)
      return packet

