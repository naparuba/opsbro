import socket

from .util import string_encode

UDP_IP = "192.168.56.104"
UDP_PORT = 18125  # curently disable


### Don't espect this part to work on your server without modifing the IP :)


# gauge = ' moncul.cpu.used : 90 |g'
# counter = ' mabite : 2 |c|@0.1'
# timer = ' montimer : 0.001 | ms'


class Stats(object):
    def __init__(self):
        self.stats = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.buf = []
    
    
    def stack(self, s):
        self.buf.append(s)
        if len(self.buf) > 20:
            pkt = string_encode('\n'.join(self.buf))
            self.sock.sendto(pkt, (UDP_IP, UDP_PORT))
            self.buf = []
    
    
    # Will increment a stat key, if None, start at 0
    def incr(self, k, v):
        self.stats[k] = self.stats.get(k, 0) + v
        s = '%s: %d |c' % (k, v)
        self.stack(s)
    
    
    # Will increment a stat key, if None, start at 0
    def timer(self, k, v):
        s = '%s: %f |ms' % (k, v)
        self.stack(s)
    
    
    def get(self, k):
        return self.stats.get(k, 0)
    
    
    def show(self):
        return ', '.join(['%s:%.4f' % (k, v) for (k, v) in self.stats.items()])


STATS = Stats()
