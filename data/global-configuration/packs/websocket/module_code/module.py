from opsbro.threadmgr import threader
from opsbro.module import ListenerModule
from opsbro.websocketmanager import websocketmgr
from opsbro.parameters import StringParameter, BoolParameter, IntParameter

from wsocket import WebSocketBackend


class WebSocketModule(ListenerModule):
    implement = 'websocket'
    
    parameters = {
        'enabled': BoolParameter(default=False),
        'port'   : IntParameter(default=6769),
        'address': StringParameter(default='0.0.0.0'),
    }
    
    
    def __init__(self):
        ListenerModule.__init__(self)
        self.websocket = {}
        self.webso = None
    
    
    def get_info(self):
        r = {}
        r['websocket_configuration'] = self.websocket
        
        if not self.webso:
            r['websocket_info'] = None
        else:
            r['websocket_info'] = self.webso.get_info()
        return r
    
    
    def prepare(self):
        self.websocket['enabled'] = self.get_parameter('enabled')
        self.websocket['port'] = self.get_parameter('port')
        self.websocket['address'] = self.get_parameter('address')
    
    
    def launch(self):
        if not self.websocket['enabled']:
            self.logger.log('Websocket object defined in the configuration is disabled, skipping websocket launch')
            return
        
        threader.create_and_launch(self.do_launch, name='Websocket port:%d listening' % self.websocket.get('port'), essential=True, part='websocket')
    
    
    def do_launch(self):
        self.webso = WebSocketBackend(self.websocket)
        # also load it in the websockermanager so other part
        # can easily forward messages
        websocketmgr.set(self.webso)
        self.webso.run()
