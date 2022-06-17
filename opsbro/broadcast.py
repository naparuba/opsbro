import threading

from .now import NOW
from .type_hint import TYPE_CHECKING
from .util import my_sort, my_cmp

if TYPE_CHECKING:
    from .type_hint import Dict

# TODO: use the lock for every call
# TODO: when stacking a message for a specific group, first check if there is a node which such a group


_MAX_MESSAGE_AGE = 900  # do not keep messages more than 15 minutes


# This will manage all broadcasts
class Broadcaster(object):
    def __init__(self):
        self.broadcasts = []
        self.broadcasts_lock = threading.RLock()
    
    
    def __sort_function(self, b1, b2):
        # type: (Dict, Dict)-> bool
        b1_send = b1['send']
        b2_send = b2['send']
        # if there is a prioritaty with 0 or 1 send (maybe the first did miss), send it in priority
        if b1.get('prioritary', False) and b1_send <= 2:
            return -1
        if b2.get('prioritary', False) and b2_send <= 2:
            return 1
        # Less send first
        return my_cmp(b1_send, b2_send)
    
    
    def append(self, msg):
        # type: (Dict)-> None
        with self.broadcasts_lock:
            msg['ctime'] = int(NOW.monotonic())
            self.broadcasts.append(msg)
    
    
    def clean_and_sort(self):
        with self.broadcasts_lock:
            # First remove messages that are too old
            too_old_limit = int(NOW.monotonic()) - _MAX_MESSAGE_AGE
            recent_messages = [msg for msg in self.broadcasts if msg['ctime'] > too_old_limit]
            # Now sort them
            self.broadcasts = my_sort(recent_messages, cmp_f=self.__sort_function)


broadcaster = Broadcaster()
