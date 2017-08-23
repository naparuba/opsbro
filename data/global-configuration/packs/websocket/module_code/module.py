from opsbro.log import logger
from opsbro.threadmgr import threader
from opsbro.module import ListenerModule
from opsbro.websocketmanager import websocketmgr
from opsbro.parameters import StringParameter, BoolParameter, IntParameter

from wsocket import WebSocketBackend


class WebSocketModule(ListenerModule):
    implement = 'websocket'
    manage_configuration_objects = ['websocket']
    parameters = {
        'enabled': BoolParameter(default=False),
        'port'   : IntParameter(default=6769),
        'address': StringParameter(default='0.0.0.0'),
    }
    
    
    def __init__(self):
        ListenerModule.__init__(self)
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
        
        threader.create_and_launch(self.do_launch, name='Websocket port:%d listening' % self.websocket.get('port', 6769), essential=True, part='websocket')
    
    
    def do_launch(self):
        self.webso = WebSocketBackend(self)
        # also load it in the websockermanager so other part
        # can easily forward messages
        websocketmgr.set(self.webso)
        self.webso.run()