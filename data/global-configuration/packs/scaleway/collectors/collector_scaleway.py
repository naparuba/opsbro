from opsbro.collector import Collector
from opsbro.hostingdrivermanager import get_hostingdrivermgr


class Scaleway(Collector):
    def launch(self):
        # We are active only if the hosting driver is scaleway
        hostingctxmgr = get_hostingdrivermgr()
        if not hostingctxmgr.is_driver_active('scaleway'):
            return False
        
        hostingctx = hostingctxmgr.get_driver('scaleway')
        # Now we have our scaleway code, we can dump info from it
        
        conf = hostingctx.get_conf()
        
        return conf
