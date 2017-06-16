from kunai.log import logger

class Zone(object):
    def __init__(self):
        pass


# Will manage the global websocket server if need
class ZoneManager(object):
    def __init__(self):
        self.zones = {}
        self._dirty_tree = True
        self.tree_top_to_bottom = {}
        self.tree_bottom_to_top = {}
    
    
    # Reset trees and compute bottom->top and top->bottom tree/indexed y the zone name
    def __relink(self):
        self._dirty_tree = True
        self.tree_top_to_bottom = {}
        self.tree_bottom_to_top = {}
        
        for (zname, zone) in self.zones.iteritems():
            print "LINK", zname, zone
            sub_zones = zone.get('sub-zones', [])
            self.tree_top_to_bottom[zname] = sub_zones
            for sub_zname in sub_zones:
                if sub_zname not in self.tree_bottom_to_top:
                    self.tree_bottom_to_top[sub_zname] = []
                self.tree_bottom_to_top[sub_zname].append(zname)
        
        print "TREE:"
        print "BOTTOM TO TOP:", self.tree_bottom_to_top
        print "TOP TO BOTTOM", self.tree_top_to_bottom
        # We are clean now
        self._dirty_tree = False
    
    
    def add(self, zone):
        name = zone.get('name', '')
        if not name:
            return
        self.zones[name] = zone
        # We did change, dirty the trees
        self._dirty_tree = True
    
    
    def get_top_zones_from(self, zname):
        # If we are dirty or never relink/not up to date, recompute the trees
        if self._dirty_tree:
            self.__relink()
        if zname not in self.tree_bottom_to_top:
            logger.error('ASKING TOP ZONES FOR unknown zone name: %s' % zname)
            return []
        return self.tree_bottom_to_top[zname]


    def get_sub_zones_from(self, zname):
        # If we are dirty or never relink/not up to date, recompute the trees
        if self._dirty_tree:
            self.__relink()
        if zname not in self.tree_top_to_bottom:
            logger.error('ASKING BOTTOM ZONES FOR unknown zone name: %s' % zname)
            return []
        return self.tree_top_to_bottom[zname]

        


zonemgr = ZoneManager()
