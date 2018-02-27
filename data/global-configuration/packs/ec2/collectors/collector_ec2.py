from opsbro.collector import Collector
from opsbro.hostingdrivermanager import get_hostingdrivermgr


class EC2(Collector):
    def launch(self):
        # We are active only if the hosting driver is scaleway
        hostingctxmgr = get_hostingdrivermgr()
        if not hostingctxmgr.is_driver_active('ec2'):
            return False
        
        hostingctx = hostingctxmgr.get_driver('ec2')
        # Now we have our scaleway code, we can dump info from it
        
        meta_data = hostingctx.get_meta_data()
        
        return meta_data
