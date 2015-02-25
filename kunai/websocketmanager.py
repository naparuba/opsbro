

# Will manage the global websocket server if need
class WebsocketManager(object):
    def __init__(self):
        self.webso = None

        
    def set(self, webso):
        self.webso = webso
        
        
    def forward(self, msg):
        if self.webso:
            self.webso.send_all(msg)

websocketmgr = WebsocketManager()
