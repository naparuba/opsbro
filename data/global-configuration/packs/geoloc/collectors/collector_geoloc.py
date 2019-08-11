from opsbro.httpclient import get_http_exceptions, httper
from opsbro.collector import Collector
from opsbro.jsonmgr import jsoner


class Geoloc(Collector):
    def __init__(self):
        super(Geoloc, self).__init__()
        self.geodata = {}
    
    
    def launch(self):
        # If already got data, keep it (do not hammering ipinfo.io api)
        if self.geodata:
            return self.geodata
        
        # Allow 3s to connect.
        # NOTE: If you lag more than 3s, means you are in north korea: then you don't need geoloc.
        try:
            data = httper.get('http://ipinfo.io/json', timeout=3)
        except get_http_exceptions() as exp:
            self.set_not_eligible("Cannot contact ipinfo.io: %s. This server does not seems to have access to internet." % exp)
            return False
        
        self.logger.debug('RAW geoloc data', data)
        self.geodata = jsoner.loads(data)
        return self.geodata
