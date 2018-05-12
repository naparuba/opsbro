import glob
import threading
import os
import json
import time

from .util import make_dir


# This class is an abstract for various manager
class BaseManager(object):
    history_directory_suffix = 'UNSET'
    
    
    def __init__(self):
        self.history_directory = None
        self._current_history_entry = []
        self._current_history_entry_lock = threading.RLock()
    
    
    def prepare_history_directory(self):
        # Prepare the history
        from .configurationmanager import configmgr
        data_dir = configmgr.get_data_dir()
        self.history_directory = os.path.join(data_dir, 'history_%s' % self.history_directory_suffix)
        self.logger.debug('Asserting existence of the history directory: %s' % self.history_directory)
        if not os.path.exists(self.history_directory):
            make_dir(self.history_directory)
    
    
    def add_history_entry(self, history_entry):
        with self._current_history_entry_lock:
            self._current_history_entry.append(history_entry)
    
    
    def write_history_entry(self):
        # Noting to do?
        if not self._current_history_entry:
            return
        # We must lock because checks can exit in others threads
        with self._current_history_entry_lock:
            now = int(time.time())
            pth = os.path.join(self.history_directory, '%d.json' % now)
            self.logger.info('Saving new collector history entry to %s' % pth)
            buf = json.dumps(self._current_history_entry)
            with open(pth, 'w') as f:
                f.write(buf)
            # Now we can reset it
            self._current_history_entry = []
    
    
    def get_history(self):
        r = []
        current_size = 0
        max_size = 1024 * 1024
        reg = self.history_directory + '/*.json'
        history_files = glob.glob(reg)
        # Get from the more recent to the older
        history_files.sort()
        history_files.reverse()
        
        # Do not send more than 1MB, but always a bit more, not less
        for history_file in history_files:
            epoch_time = int(os.path.splitext(os.path.basename(history_file))[0])
            with open(history_file, 'r') as f:
                e = json.loads(f.read())
            r.append({'date': epoch_time, 'entries': e})
            
            # If we are now too big, return directly
            size = os.path.getsize(history_file)
            current_size += size
            if current_size > max_size:
                # Give older first
                r.reverse()
                return r
        # give older first
        r.reverse()
        return r
