import os
import sys

from opsbro.collector import Collector


class Selinux(Collector):
    def launch(self):
        self.logger.debug('getSelinux: start')
        
        if sys.platform != 'linux2':
            self.set_not_eligible('SeLinux is only available on linux. not kidding.')
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
        
        self.logger.debug('getSelinux: completed, returning')
        return res
