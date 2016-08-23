import sys
import traceback
from kunai.log import logger
from kunai.collector import Collector


class IoStats(Collector):
    def launch(self):
        # logger.debug('get_open_ports: start')

        open_ports = {'tcp': [], 'udp': []}

        if sys.platform != 'linux2':
            logger.debug('get_open_ports: unsupported platform')
            return False

        # logger.debug('get_open_ports: linux2')

        
        try:
            _cmd = 'netstat -tuln'
            netstat = self.execute_shell(_cmd)
            if not netstat:
                logger.error('get_open_ports: exception in launching command')
                return False
            
            for line in netstat.splitlines():
                line = line.strip()

                # Will be something like
                # tcp        0      0 0.0.0.0:27017           0.0.0.0:*               LISTEN
                if not line.startswith('tcp') and not line.startswith('udp'):
                    # Not a good line, skip it
                    continue
                # print "LOOKING AT LINE"
                elts = [e for e in line.split(' ') if e]
                # print "ELEMENTS", elts
                if len(elts) != 6:
                    # print "BAD LINE", elts
                    continue

                open_port = {}
                open_port['proto'] = elts[0]
                open_port['source'] = elts[3]
                open_port['dest'] = elts[4]
                open_port['state'] = elts[5]

                if open_port['proto'].startswith('tcp'):
                    open_ports['tcp'].append(open_port)
                elif open_port['proto'].startswith('udp'):
                    open_ports['udp'].append(open_port)
                else:
                    print "Unknown protocol??"

        except Exception:
            logger.error('get_open_ports: exception = %s', traceback.format_exc())
            return False

        # logger.debug('get_open_ports: completed, returning')
        return open_ports
