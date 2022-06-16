from opsbro.collector import Collector


class OpenPorts(Collector):
    def launch(self):
        open_port_details = {'tcp': [], 'udp': []}
        open_ports = set()  # just the bunch of int
        
        if not hasattr(self, 'psutil_lib'):
            try:
                import psutil
                self.psutil_lib = psutil
            except ImportError as exp:
                self.set_not_eligible('get_open_ports: cannot import psutil lib %s. Please install it.' % exp)
                return False

        if not hasattr(self.psutil_lib, 'net_connections'):  # old lib version
            self.set_not_eligible('get_open_ports: the psutil lib version is too old, plase update it.')
            return False

        listening_connexions = [con for con in self.psutil_lib.net_connections() if con.status == 'LISTEN']
        for con in listening_connexions:
            # UDP: sconn(fd=7, family=10, type=1, laddr=('::', 53)
            # TCP: sconn(fd=26, family=2, type=1, laddr=('0.0.0.0', 6769), raddr=(), status='LISTEN', pid=26)
            if len(con.laddr) != 2:  # bad format
                continue
            laddr = con.laddr[0]
            lport = con.laddr[1]
            open_ports.add(lport)
            
            if con.family == 10:  # UDP
                open_port_details['udp'].append(laddr)
            else:
                open_port_details['tcp'].append(laddr)
        
        open_ports = list(open_ports)
        open_ports.sort()
        return {'ports': open_ports, 'details': open_port_details}
