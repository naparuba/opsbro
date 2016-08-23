import sys
import os
from kunai.log import logger
from kunai.collector import Collector


class Sshd(Collector):
    def launch(self):
        logger.debug('get_sshd: starting')
        res = {}
        if os.path.exists('/etc/ssh/ssh_host_rsa_key.pub'):
            f = open('/etc/ssh/ssh_host_rsa_key.pub', 'r')
            buf = f.read().strip()
            f.close()
            res['host_rsa_key_pub'] = buf.replace('ssh-rsa ', '')
        if os.path.exists('/etc/ssh/ssh_host_dsa_key.pub'):
            f = open('/etc/ssh/ssh_host_dsa_key.pub', 'r')
            buf = f.read().strip()
            f.close()
            res['host_dsa_key_pub'] = buf.replace('ssh-dss ', '')
        
        return res
