from opsbro.collector import Collector


class Imrane(Collector):
    def __init__(self):
        super(Imrane, self).__init__()
        self.data = {}
    
    
    def launch(self):
        # If already got data, keep it (do not hammering ipinfo.io api)
        if self.data:
            return self.data
        self.data['toto'] = 'titi'
        return self.data
