import threading


# TODO: use the lock for every call
# TODO: when stacking a message for a specific group, first check if there is a node which such a group

# This will manage all broadcasts
class Broadcaster(object):
    def __init__(self):
        self.broadcasts = []
        self.broadcasts_lock = threading.RLock()
    
    
    def __sort_function(self, b1, b2):
        b1_send = b1['send']
        b2_send = b2['send']
        # if there is a prioritaty with 0 or 1 send (maybe the first did miss), send it in priority
        if b1.get('prioritary', False) and b1_send <= 2:
            return -1
        if b2.get('prioritary', False) and b2_send <= 2:
            return 1
        # Less send first
        return cmp(b1_send, b2_send)
    
    
    def append(self, msg):
        with self.broadcasts_lock:
            self.broadcasts.append(msg)
    
    
    def sort(self):
        with self.broadcasts_lock:
            self.broadcasts.sort(cmp=self.__sort_function)


broadcaster = Broadcaster()
