import sys
import traceback

from opsbro.collector import Collector


class OpenPorts(Collector):
    def launch(self):
        logger = self.logger
        # logger.debug('get_open_ports: start')
        
        open_port_details = {'tcp': [], 'udp': []}
        open_ports = set()  # just the bunch of int
        
        if sys.platform != 'linux2':
            logger.debug('get_open_ports: unsupported platform')
            return False
        
        try:
            _cmd = 'netstat -tuln'
            try:
                netstat = self.execute_shell(_cmd)
            except Exception as exp:
                self.set_error('get_open_ports: exception in launching command: %s' % exp)
                return False
            if netstat is False:
                return False
            
            for line in netstat.splitlines():
                line = line.strip()
                
                # Will be something like
                # tcp        0      0 0.0.0.0:27017           0.0.0.0:*               LISTEN
                if not line.startswith('tcp') and not line.startswith('udp'):
                    # Not a good line, skip it
                    continue
                
                elts = [e for e in line.split(' ') if e]
                
                if len(elts) != 6:  # bad line
                    continue
                
                if elts[5] != 'LISTEN':  # not a listen port
                    continue
                
                open_port = {}
                open_port['proto'] = elts[0]
                open_port['source'] = elts[3]
                open_port['dest'] = elts[4]
                open_port['state'] = elts[5]
                
                # no : mean no port
                if ':' not in open_port['source']:
                    continue
                
                _port = int(open_port['source'].split(':')[-1])
                open_ports.add(_port)
                
                if open_port['proto'].startswith('tcp'):
                    open_port_details['tcp'].append(open_port)
                elif open_port['proto'].startswith('udp'):
                    open_port_details['udp'].append(open_port)
                else:
                    print "Unknown protocol??"
        
        except Exception:
            self.set_error('get_open_ports: exception = %s' % traceback.format_exc())
            return False
        
        open_ports = list(open_ports)
        open_ports.sort()
        
        # logger.debug('get_open_ports: completed, returning')
        return {'ports': open_ports, 'details': open_port_details}
