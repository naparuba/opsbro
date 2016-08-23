import json
import requests
from kunai.log import logger
from kunai.collector import Collector


class Geoloc(Collector):
    def __init__(self, config, put_result=None):
        super(Geoloc, self).__init__(config, put_result)
        self.geodata = {}
    
    
    def launch(self):
        # If already got data, keep it (do not hammering ipinfo.io api)
        if self.geodata:
            return self.geodata
        try:
            r = requests.get('http://ipinfo.io/json')
        except Exception, exp:
            logger.debug('[GEOLOC] error: %s' % exp)
            return None
        data = r.text
        logger.debug('RAW geoloc data', data)
        self.geodata = json.loads(data)
        return self.geodata
