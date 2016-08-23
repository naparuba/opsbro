import os
import sys
import commands
import re
from kunai.log import logger
from kunai.collector import Collector
from kunai.util import get_public_address


# TODO: look at /sys/class/dmi/id/ for information

class Dmidecode(Collector):
    def launch(self):
        logger.debug('getDmidecode: start')
        res = {}
        for p in commands.getoutput('dmidecode -s').split('\n'):
            if re.search('^ ', p):
                res[p.replace('-', '_').strip()] = commands.getoutput('dmidecode -s %s' % p)
        logger.debug('getdmidecode: completed, returning')
        return res
