from opsbro.collector import Collector
from opsbro.hostingcontextmanager import get_hostingcontextmgr


class GoogleCloud(Collector):
    def launch(self):
        # We are active only if the hosting context is scaleway
        hostingctxmgr = get_hostingcontextmgr()
        if not hostingctxmgr.is_context_active('google-cloud'):
            return False
        
        hostingctx = hostingctxmgr.get_context()
        # Now we have our scaleway code, we can dump info from it
        
        meta_data = hostingctx.get_meta_data()
        
        return meta_data
