import time
from kunai.log import logger
from kunai.collector import Collector


class Redis(Collector):
    RATE_KEYS = ['used_cpu_sys', 'used_cpu_sys_children', 'used_cpu_user', 'used_cpu_user_children',
                 'total_commands_processed']


    def __init__(self, config, put_result=None):
        super(Redis, self).__init__(config, put_result)
        self.store = {}
        self.last_launch = 0.0
    
    
    def launch(self):
        try:
            import redis
        except ImportError:
            logger.debug('Unable to import redis library')
            return {'available': False}

        now = int(time.time())
        diff = now - self.last_launch
        self.last_launch = now

        conn = redis.Redis()
        
        start = time.time()
        try:
            info = conn.info()
        except ValueError, e:
            raise
        except redis.ConnectionError, exp:
            logger.info('Redis connexion fail: %s' % exp)
            return {'available': False}
        except Exception, e:
            raise

        latency_ms = round((time.time() - start) * 1000, 2)
        info['connexion_latency_ms'] = latency_ms
        info['available'] = True

        to_add = {}
        for (k, v) in info.iteritems():
            if k in self.RATE_KEYS:
                if k in self.store:
                    to_add['%s/s' % k] = (v - self.store[k]) / diff
                else:
                    to_add['%s/s' % k] = 0
                self.store[k] = info[k]

        for k in self.RATE_KEYS:
            del info[k]
        info.update(to_add)

        return info
