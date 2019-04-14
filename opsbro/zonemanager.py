import os
import threading

from .library import libstore
from .log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('configuration')


class Zone(object):
    def __init__(self):
        pass


# When you have more than 32 zones level, you fuck up with a loop in fact :)
MAX_ZONE_LEVELS = 32


# Will manage the global websocket server if need
class ZoneManager(object):
    def __init__(self):
        self.zones = {}
        self.zones_lock = threading.RLock()
        self._dirty_tree = True
        self.tree_top_to_bottom = {}
        self.tree_bottom_to_top = {}
    
    
    # Reset trees and compute bottom->top and top->bottom tree/indexed y the zone name
    # but in a recursive way so we will have ALL bottom and all TOP zones for each zone
    def __relink(self):
        with self.zones_lock:
            self._dirty_tree = True
            self.tree_top_to_bottom = {}
            self.tree_bottom_to_top = {}
            
            for zname in self.zones:
                sub_zone_set = set()
                self.__get_sub_zones_rec(zname, sub_zone_set, 0)
                self.tree_top_to_bottom[zname] = sub_zone_set
                self.tree_bottom_to_top[zname] = set()  # prepare the next loop
            
            for (zname, sub_zones) in self.tree_top_to_bottom.items():
                for sub_zone_name in sub_zones:
                    self.tree_bottom_to_top[sub_zone_name].add(zname)
            
            # We are clean now
            self._dirty_tree = False
    
    
    # NOTE1: the sub_zones_set will MUTATE between calls, that's why it's a pointer
    #        => yes, I don't give a fuck about a "golden imutability rule" here, I'm in a lock and 2 functions
    # NOTE2: it's not optimal as we will loop a lot even for each sub zone, but we won't have so much
    def __get_sub_zones_rec(self, zname, sub_zones_set, level):
        zone = self.zones.get(zname, None)
        # Missing zone, don't care about it, it was error if I don't break it
        if zone is None:
            return
        if level > MAX_ZONE_LEVELS:
            return
        sub_zones = zone.get('sub-zones', [])
        for sub_zone_name in sub_zones:
            sub_zone = self.zones.get(sub_zone_name, None)
            if sub_zone is None:
                continue
            # add this sub zone in the parent set
            sub_zones_set.add(sub_zone_name)
            # and loop below
            self.__get_sub_zones_rec(sub_zone_name, sub_zones_set, level + 1)
    
    
    def add_zone(self, zone):
        name = zone.get('name', '')
        if not name:
            return
        self.zones[name] = zone
        # We did change, dirty the trees
        self._dirty_tree = True
        
        # If the zone have a key, load it into the encrypter so we will be
        # able to use it to exchange with this zone
        # The key can be a file in the zone key directory, with the name of the zone.key
        encrypter = libstore.get_encrypter()
        encrypter.load_or_reload_key_for_zone_if_need(name)
    
    
    def get_top_zones_from(self, zname):
        # If we are dirty or never relink/not up to date, recompute the trees
        if self._dirty_tree:
            self.__relink()
        if zname not in self.tree_bottom_to_top:
            return []
        return self.tree_bottom_to_top[zname]
    
    
    def is_top_zone_from(self, from_zone, checked_zone):
        top_zones = self.get_top_zones_from(from_zone)
        return checked_zone in top_zones
    
    
    def get_sub_zones_from(self, zname):
        # If we are dirty or never relink/not up to date, recompute the trees
        if self._dirty_tree:
            self.__relink()
        if zname not in self.tree_top_to_bottom:
            return []
        return self.tree_top_to_bottom[zname]
    
    
    def is_sub_zone_from(self, from_zone, checked_zone):
        sub_zones = self.get_sub_zones_from(from_zone)
        return checked_zone in sub_zones
    
    
    def is_direct_sub_zone_from(self, from_zone_name, checked_zone_name):
        from_zone = self.zones.get(from_zone_name, None)
        if from_zone is None:
            return False
        sub_zones = from_zone.get('sub-zones', [])
        return checked_zone_name in sub_zones
    
    def get_zones(self):
        return self.zones
    
    
    def have_zone(self, zname):
        return zname in self.zones


zonemgr = ZoneManager()
