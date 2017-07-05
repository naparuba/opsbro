import httplib  # Used only for handling httplib.HTTPException (case #26701)
import re
import urllib2
import traceback

from kunai.collector import Collector


class Nginx(Collector):
    def launch(self):
        logger = self.logger
        
        logger.debug('getNginxStatus: start')
        
        if 'nginxStatusUrl' in self.config and self.config[
            'nginxStatusUrl'] != 'http://www.example.com/nginx_status':  # Don't do it if the status URL hasn't been provided
            logger.debug('getNginxStatus: config set')
            
            try:
                logger.debug('getNginxStatus: attempting urlopen')
                
                req = urllib2.Request(self.config['nginxStatusUrl'], None, {})
                
                # Do the request, log any errors
                request = urllib2.urlopen(req)
                response = request.read()
            
            except urllib2.HTTPError, e:
                logger.error('Unable to get Nginx status - HTTPError = %s', e)
                return False
            
            except urllib2.URLError, e:
                logger.error('Unable to get Nginx status - URLError = %s', e)
                return False
            
            except httplib.HTTPException, e:
                logger.error('Unable to get Nginx status - HTTPException = %s', e)
                return False
            
            except Exception, e:
                logger.error('Unable to get Nginx status - Exception = %s', traceback.format_exc())
                return False
            
            logger.debug('getNginxStatus: urlopen success, start parsing')
            
            # Thanks to http://hostingfu.com/files/nginx/nginxstats.py for this code
            
            logger.debug('getNginxStatus: parsing connections')
            
            try:
                # Connections
                parsed = re.search(r'Active connections:\s+(\d+)', response)
                connections = int(parsed.group(1))
                
                logger.debug('getNginxStatus: parsed connections')
                logger.debug('getNginxStatus: parsing reqs')
                
                # Requests per second
                parsed = re.search(r'\s*(\d+)\s+(\d+)\s+(\d+)', response)
                
                if not parsed:
                    logger.debug('getNginxStatus: could not parse response')
                    return False
                
                requests = int(parsed.group(3))
                
                logger.debug('getNginxStatus: parsed reqs')
                
                if self.nginxRequestsStore == None or self.nginxRequestsStore < 0:
                    logger.debug('getNginxStatus: no reqs so storing for first time')
                    self.nginxRequestsStore = requests
                    requestsPerSecond = 0
                else:
                    logger.debug('getNginxStatus: reqs stored so calculating')
                    logger.debug('getNginxStatus: self.nginxRequestsStore = %s', self.nginxRequestsStore)
                    logger.debug('getNginxStatus: requests = %s', requests)
                    
                    requestsPerSecond = float(requests - self.nginxRequestsStore) / 60
                    logger.debug('getNginxStatus: requestsPerSecond = %s', requestsPerSecond)
                    self.nginxRequestsStore = requests
                
                if connections != None and requestsPerSecond != None:
                    logger.debug('getNginxStatus: returning with data')
                    return {'connections': connections, 'reqPerSec': requestsPerSecond}
                else:
                    logger.debug('getNginxStatus: returning without data')
                    return False
            
            except Exception:
                logger.error('Unable to get Nginx status - %s - Exception = %s', response, traceback.format_exc())
                return False
        
        else:
            logger.debug('getNginxStatus: config not set')
            
            return False
