from opsbro.collector import Collector
from opsbro.gossip import gossiper


class Gossip(Collector):
    
    def __init__(self):
        super(Gossip, self).__init__()
    
    
    def launch(self):
        data = {'zone': gossiper.get_zone_from_node(), 'nb_known_nodes': gossiper.get_number_of_nodes()}
        return data
