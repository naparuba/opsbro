import json
import httplib
import socket

from opsbro.collector import Collector


class Geoloc(Collector):
    def __init__(self):
        super(Geoloc, self).__init__()
        self.geodata = {}
    
    
    def launch(self):
        # If already got data, keep it (do not hammering ipinfo.io api)
        if self.geodata:
            return self.geodata
        
        srv = 'ipinfo.io'
        # Allow 3s to connect.
        # NOTE: If you lag more than 3s, means you are in north korea: then you don't need geoloc.
        try:
            conn = httplib.HTTPConnection(srv, timeout=3)
            conn.request("GET", "/json")
            r1 = conn.getresponse()
            data = r1.read()
        except socket.gaierror, exp:
            self.error("Cannot contact ipinfo.io: %s" % exp)
            return False
        
        self.logger.debug('RAW geoloc data', data)
        self.geodata = json.loads(data)
        return self.geodata
