import os
import commands
import re

from opsbro.collector import Collector


# DMI have lot of useful information that detectors can use to know lot about the platform/hardware
class Dmidecode(Collector):
    def launch(self):
        logger = self.logger
        logger.debug('getDmidecode: start')
        res = {}
        
        # Maybe we are in linux and we can directly read the
        linux_dmi_path = '/sys/class/dmi/id/'
        if os.path.exists(linux_dmi_path):
            file_names = os.listdir(linux_dmi_path)
            for fname in file_names:
                p = os.path.join(linux_dmi_path, fname)
                # There can be a link there, skip them
                if os.path.isfile(p):
                    f = open(p, 'r')
                    buf = f.read()
                    f.close()
                    res[fname] = buf.strip()
            logger.debug('getdmidecode: completed, returning')
            return res
        # Ok not direct access, try to launch with
        else:  # try dmidecode way, if exists
            for p in commands.getoutput('LANG=C dmidecode -s').split('\n'):
                if re.search('^ ', p):
                    buf = commands.getoutput('LANG=C dmidecode -s %s' % p).strip()
                    if 'No such file or directory' in buf:
                        logger.warning('Cannot access to dmi information with dmidecode command, exiting this collector.')
                        return res
                    res[p.replace('-', '_').strip()] = buf
            logger.debug('getdmidecode: completed, returning')
            return res
