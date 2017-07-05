import httplib
import urllib2
import traceback
import json

from kunai.collector import Collector


class RabbitMQ(Collector):
    def launch(self):
        logger = self.logger
        logger.debug('getRabbitMQStatus: start')
        
        if 'rabbitMQStatusUrl' not in self.config or \
                        'rabbitMQUser' not in self.config or \
                        'rabbitMQPass' not in self.config or \
                        self.config['rabbitMQStatusUrl'] == 'http://www.example.com:55672/json':
            
            logger.debug('getRabbitMQStatus: config not set')
            return False
        
        logger.debug('getRabbitMQStatus: config set')
        
        try:
            logger.debug('getRabbitMQStatus: attempting authentication setup')
            
            manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
            manager.add_password(None, self.config['rabbitMQStatusUrl'], self.config['rabbitMQUser'],
                                 self.config['rabbitMQPass'])
            handler = urllib2.HTTPBasicAuthHandler(manager)
            opener = urllib2.build_opener(handler)
            urllib2.install_opener(opener)
            
            logger.debug('getRabbitMQStatus: attempting urlopen')
            req = urllib2.Request(self.config['rabbitMQStatusUrl'], None, {})
            
            # Do the request, log any errors
            request = urllib2.urlopen(req)
            response = request.read()
        
        except urllib2.HTTPError, e:
            logger.error('Unable to get RabbitMQ status - HTTPError = %s', e)
            return False
        
        except urllib2.URLError, e:
            logger.error('Unable to get RabbitMQ status - URLError = %s', e)
            return False
        
        except httplib.HTTPException, e:
            logger.error('Unable to get RabbitMQ status - HTTPException = %s', e)
            return False
        
        except Exception:
            logger.error('Unable to get RabbitMQ status - Exception = %s', traceback.format_exc())
            return False
        
        try:
            status = json.loads(response)
            
            logger.debug(status)
            
            if 'connections' not in status:
                # We are probably using the newer RabbitMQ 2.x status plugin, so try to parse that instead.
                status = {}
                logger.debug('getRabbitMQStatus: using 2.x management plugin data')
                import urlparse
                
                split_url = urlparse.urlsplit(self.config['rabbitMQStatusUrl'])
                
                # Connections
                url = split_url[0] + '://' + split_url[1] + '/api/connections'
                logger.debug('getRabbitMQStatus: attempting urlopen on %s', url)
                manager.add_password(None, url, self.config['rabbitMQUser'], self.config['rabbitMQPass'])
                req = urllib2.Request(url, None, {})
                # Do the request, log any errors
                request = urllib2.urlopen(req)
                response = request.read()
                
                connections = json.loads(response)
                
                status['connections'] = len(connections)
                logger.debug('getRabbitMQStatus: connections = %s', status['connections'])
                
                # Queues
                url = split_url[0] + '://' + split_url[1] + '/api/queues'
                logger.debug('getRabbitMQStatus: attempting urlopen on %s', url)
                manager.add_password(None, url, self.config['rabbitMQUser'], self.config['rabbitMQPass'])
                req = urllib2.Request(url, None, {})
                # Do the request, log any errors
                request = urllib2.urlopen(req)
                response = request.read()
                
                queues = json.loads(response)
                
                status['queues'] = queues
                logger.debug(status['queues'])
        
        except Exception:
            logger.error('Unable to load RabbitMQ status JSON - Exception = %s', traceback.format_exc())
            return False
        
        logger.debug('getRabbitMQStatus: completed, returning')
        
        # Fix for queues with the same name (case 32788)
        for queue in status.get('queues', []):
            vhost = queue.get('vhost', '/')
            if vhost == '/':
                continue
            
            queue['name'] = '%s/%s' % (vhost, queue['name'])
        
        return status
