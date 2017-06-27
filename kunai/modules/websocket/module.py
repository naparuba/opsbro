from kunai.log import logger
from kunai.threadmgr import threader
from kunai.module import Module
from kunai.websocketmanager import websocketmgr

from wsocket import WebSocketBackend


class WebSocketModule(Module):
    implement = 'websocket'
    manage_configuration_objects = ['websocket']
    
    
    def __init__(self):
        Module.__init__(self)
        self.websocket = None
        self.listening_addr = ''
    
    
    def import_configuration_object(self, object_type, o, mod_time, fname, short_name):
        self.websocket = o
    
    
    # Prepare to open the UDP port
    def prepare(self):
        # import listening addr from the daemon
        self.listening_addr = self.daemon.listening_addr
    
    
    def get_info(self):
        r = {}
        if self.websocket is None:
            r['websocket_configuration'] = None
        else:
            r['websocket_configuration'] = self.websocket
        if not self.webso:
            r['websocket_info'] = None
        else:
            r['websocket_info'] = self.webso.get_info()
        return r
    
    
    def launch(self):
        if self.websocket is None:
            logger.log('No websocket object defined in the configuration, skipping it')
            return
        if not self.websocket['enabled']:
            logger.log('Websocket object defined in the configuration is disabled, skipping websocket launch')
            return
        
        threader.create_and_launch(self.do_launch, name='[Websocket] Websocket port:%d listening' % self.websocket.get('port', 6769), essential=True)
    
    
    def do_launch(self):
        self.webso = WebSocketBackend(self)
        # also load it in the websockermanager so other part
        # can easily forward messages
        websocketmgr.set(self.webso)
        self.webso.run()
