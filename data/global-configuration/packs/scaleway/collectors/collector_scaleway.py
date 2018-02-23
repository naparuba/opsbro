from opsbro.collector import Collector
from opsbro.hostingcontextmanager import get_hostingcontextmgr


class Scaleway(Collector):
    def launch(self):
        # We are active only if the hosting context is scaleway
        hostingctxmgr = get_hostingcontextmgr()
        if not hostingctxmgr.is_context_active('scaleway'):
            return False
        
        hostingctx = hostingctxmgr.get_context()
        # Now we have our scaleway code, we can dump info from it
        
        conf = hostingctx.get_conf()
        
        return conf
