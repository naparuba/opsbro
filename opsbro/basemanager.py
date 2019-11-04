import glob
import threading
import os
import time

from .util import make_dir, epoch_to_human_string
from .jsonmgr import jsoner


# This class is an abstract for various manager
class BaseManager(object):
    history_directory_suffix = 'UNSET'
    history_files_keep_delay = 86400 * 15  # by default keep 15 days of files
    history_files_clean_interval = 3600
    
    
    def __init__(self, logger):
        self.logger = logger
        self.history_directory = None
        self._current_history_entry = []
        self._current_history_entry_lock = threading.RLock()
        # Clean
        self._last_history_files_clean = 0.0  # clean files at startup
    
    
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
            self.logger.debug('Saving new collector history entry to %s' % pth)
            buf = jsoner.dumps(self._current_history_entry)
            with open(pth, 'w') as f:
                f.write(buf)
            # Now we can reset it
            self._current_history_entry = []
        
        if self._last_history_files_clean < now - self.history_files_clean_interval:
            self._clean_history_files()
    
    
    def _clean_history_files(self):
        now = int(time.time())
        self._last_history_files_clean = now
        clean_limit = now - self.history_files_keep_delay
        
        # Look at the databses directory that have the hour time set
        subfiles = os.listdir(self.history_directory)
        
        nb_file_cleaned = 0
        for subfile in subfiles:
            subfile_minute = subfile.replace('.json', '')
            try:
                file_minute = int(subfile_minute)
            except ValueError:  # who add a dir that is not a int here...
                continue
            # Is the hour available for cleaning?
            if file_minute < clean_limit:
                fpath = os.path.join(self.history_directory, subfile)
                try:
                    os.unlink(fpath)
                    nb_file_cleaned += 1
                except Exception as exp:
                    self.logger.error('Cannot remove history file %s : %s' % (fpath, exp))
        if nb_file_cleaned != 0:
            self.logger.info("We did cleaned %d history files older than %s" % (nb_file_cleaned, epoch_to_human_string(clean_limit)))
    
    
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
                e = jsoner.loads(f.read())
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
