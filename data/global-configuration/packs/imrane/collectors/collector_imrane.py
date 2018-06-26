import json
import httplib
import socket

from opsbro.collector import Collector


class Imrane(Collector):
    def __init__(self):
        super(Imrane, self).__init__()
        self.data = {}
    
    
    def launch(self):
        # If already got data, keep it (do not hammering ipinfo.io api)
        if self.data:
            return self.data
        self.data['toto'] = 'titi'
        return self.data

        srv = 'ipinfo.io'
        # Allow 3s to connect.
        # NOTE: If you lag more than 3s, means you are in north korea: then you don't need geoloc.
        try:
            conn = httplib.HTTPConnection(srv, timeout=3)
            conn.request("GET", "/json")
            r1 = conn.getresponse()
            data = r1.read()
        except socket.gaierror as exp:
            self.set_not_eligible("Cannot contact ipinfo.io: %s. This server seems to have access to internet." % exp)
            return False
        
        self.logger.debug('RAW geoloc data', data)
        self.geodata = json.loads(data)
        return self.geodata
