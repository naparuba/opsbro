import sys
import os
import commands
from kunai.log import logger
from kunai.collector import Collector


class Virtual(Collector):
    def launch(self):
        logger.debug('getVirtual: starting')
        res = {'virtual': 'false'}
        if os.name == 'nt':
        	return res
        status, output = commands.getstatusoutput('virt-what')
        if status != 0:
            logger.debug('getVirtual: no virt-what: %s' % output)
            return res
        res['virtual'] = output
        return res
