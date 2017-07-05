import os
import re
import commands

from kunai.collector import Collector


def extract(input):
    mo = re.search(r'^(?P<interface>eth\d+|eth\d+:\d+)\s+' +
                   r'Link encap:(?P<link_encap>\S+)\s+' +
                   r'(HWaddr\s+(?P<hardware_address>\S+))?' +
                   r'(\s+inet addr:(?P<ip_address>\S+))?' +
                   r'(\s+Bcast:(?P<broadcast_address>\S+)\s+)?' +
                   r'(Mask:(?P<net_mask>\S+)\s+)?',
                   input, re.MULTILINE)
    if mo:
        info = mo.groupdict('')
        info['running'] = False
        info['up'] = False
        info['multicast'] = False
        info['broadcast'] = False
        if 'RUNNING' in input:
            info['running'] = True
        if 'UP' in input:
            info['up'] = True
        if 'BROADCAST' in input:
            info['broadcast'] = True
        if 'MULTICAST' in input:
            info['multicast'] = True
        return info
    return {}


# interfaces = [ extract(interface) for interface in ifconfig.split('\n\n') if interface.strip() ]
# print json.dumps(interfaces, indent=4)


class Interfaces(Collector):
    def launch(self):
        logger = self.logger
        logger.debug('getInterfaces: start')
        
        res = {}
        for pth in ["/bin/ifconfig", "/sbin/ifconfig", "/usr/sbin/ifconfig"]:
            if os.path.exists(pth):
                status, output = commands.getstatusoutput('%s -a' % pth)
                if status != 0:
                    return res
                paragraphs = output.split('\n\n')
                for p in paragraphs:
                    r = extract(p.strip())
                    if 'interface' in r:
                        res[r['interface']] = r
                return res
        
        return res
