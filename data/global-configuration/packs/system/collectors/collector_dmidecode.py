import os
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
        elif os.name == 'nt':
            self.set_not_eligible('Windows is currently not managed for DMI informations')
            return False
        # Ok not direct access, try to launch with
        else:  # try dmidecode way, if exists
            res = self.execute_shell('LANG=C dmidecode -s')
            if res is False:
                self.set_not_eligible('Cannot read dmi information')
                return False
            for p in res.split('\n'):
                if re.search('^ ', p):
                    buf = self.execute_shell('LANG=C dmidecode -s %s' % p).strip()
                    if 'No such file or directory' in buf:
                        logger.warning('Cannot access to dmi information with dmidecode command, exiting this collector.')
                        self.set_not_eligible('Cannot get DMI informations because the dmidecode command is missing.')
                        return res
                    res[p.replace('-', '_').strip()] = buf
            logger.debug('getdmidecode: completed, returning')
            return res
