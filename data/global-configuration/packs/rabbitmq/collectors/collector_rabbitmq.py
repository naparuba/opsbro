import traceback
import json

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.collector import Collector
from opsbro.parameters import StringParameter


# TODO: look at all available at to learn how rabbitmq is working https://github.com/nagios-plugins-rabbitmq/nagios-plugins-rabbitmq

class RabbitMQ(Collector):
    parameters = {
        'uri'     : StringParameter(default='http://localhost:15672/api/overview'),
        'user'    : StringParameter(default='guest'),
        'password': StringParameter(default='guest'),
        
    }
    
    
    def launch(self):
        logger = self.logger
        logger.debug('getRabbitMQStatus: start')
        
        if not self.is_in_group('rabbitmq'):
            self.set_not_eligible('Please add the rabbitmq group to enable this collector.')
            return
        
        # uri = 'http://localhost:15672/api/overview'
        # user = 'guest'
        # password = 'guest'
        
        try:
            '''
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
            '''
            
            uri = self.get_parameter('uri')
            user = self.get_parameter('user')
            password = self.get_parameter('password')
            response = httper.get(uri, timeout=3, user=user, password=password)
        
        except get_http_exceptions() as e:
            self.set_error('Unable to get RabbitMQ status - HTTPError = %s' % e)
            return False
        
        except Exception:
            self.set_error('Unable to get RabbitMQ status - Exception = %s' % traceback.format_exc())
            return False
        
        try:
            status = json.loads(response)
        except Exception as exp:
            self.set_error("Rabbitmq: parsing json: %s" % exp)
            return False
        
        return status
