import os
import sys
from kunai.log import logger
from kunai.collector import Collector


class Selinux(Collector):
    def launch(self):
        logger.debug('getSelinux: start')

        if sys.platform != 'linux2':
            return {}

        res = {'enabled': False, 'mode': 'disabled'}
        if os.path.exists('/selinux/enforce'):
            res['enabled'] = True
        else:
            res['enabled'] = False
            return res
        f = open('/selinux/enforce', 'r')
        buf = f.read().strip()
        f.close()
        if buf == '1':
            res['mode'] = 'enforcing'

        logger.debug('getSelinux: completed, returning')
        return res
