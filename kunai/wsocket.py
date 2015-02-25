import json
from websocketserver import WebSocket, SimpleWebSocketServer




class WebExporter(WebSocket):
    def handleMessage(self):
        if self.data is None:
            self.data = ''

    def handleConnected(self):
        print self.address, 'connected'

    def handleClose(self):
        print self.address, 'closed'


class WebSocketBackend(object):
    def __init__(self, clust):
        self.clust = clust
        port = clust.websocket.get('port', 6769)
        self.server = SimpleWebSocketServer(clust.listening_addr, port, WebExporter)


    def run(self):
	self.server.serveforever()


    def get_info(self):
        return {'nb_connexions': len(self.server.connections)}
    

    def send_all(self, o):
        try:
            msg = json.dumps(o)
        except ValueError:
            return
        for client in self.server.connections.itervalues():
            try:
                client.sendMessage(msg)
            except Exception as exp:
                logger.error('Cannot send websocket message: %s' % exp, part='websocket')
        
