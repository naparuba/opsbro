import json
import requests

from opsbro.collector import Collector


class Geoloc(Collector):
    def __init__(self):
        super(Geoloc, self).__init__()
        self.geodata = {}
    
    
    def launch(self):
        # If already got data, keep it (do not hammering ipinfo.io api)
        if self.geodata:
            return self.geodata
        try:
            r = requests.get('http://ipinfo.io/json')
        except Exception, exp:
            self.logger.debug('[GEOLOC] error: %s' % exp)
            return None
        data = r.text
        self.logger.debug('RAW geoloc data', data)
        self.geodata = json.loads(data)
        return self.geodata
