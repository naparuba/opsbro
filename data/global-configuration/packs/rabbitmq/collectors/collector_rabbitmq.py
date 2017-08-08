import httplib
import urllib2
import traceback
import json

from opsbro.collector import Collector
from opsbro.parameters import StringParameter, IntParameter


# TODO: look at all available at to learn how rabbitmq is working https://github.com/nagios-plugins-rabbitmq/nagios-plugins-rabbitmq

class RabbitMQ(Collector):
    parameters = {
        'uri'     : StringParameter(default='http://localhost:15672/api/overview'),
        'user'    : StringParameter(default='root'),
        'password': StringParameter(default=''),
        
    }
    
    
    def launch(self):
        logger = self.logger
        logger.debug('getRabbitMQStatus: start')
        
        uri = 'http://localhost:15672/api/overview'
        user = 'guest'
        password = 'guest'
        
        try:
            logger.debug('getRabbitMQStatus: attempting authentication setup')
            
            manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
            manager.add_password(None, uri, user, password)
            handler = urllib2.HTTPBasicAuthHandler(manager)
            opener = urllib2.build_opener(handler)
            urllib2.install_opener(opener)
            
            logger.debug('getRabbitMQStatus: attempting urlopen')
            req = urllib2.Request(uri, None, {})
            
            # Do the request, log any errors
            request = urllib2.urlopen(req)
            response = request.read()
        
        except (urllib2.HTTPError, urllib2.URLError, httplib.HTTPException) as e:
            logger.error('Unable to get RabbitMQ status - HTTPError = %s' % e)
            return False
        
        except Exception:
            logger.error('Unable to get RabbitMQ status - Exception = %s', traceback.format_exc())
            return False
        
        try:
            status = json.loads(response)
        except Exception, exp:
            logger.error("Rabbitmq: parsing json: %s" % exp)
            return False
        
        return status
