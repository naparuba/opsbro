from .log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('daemon')


class ProcessTitleManager(object):
    def __init__(self):
        try:
            from setproctitle import setproctitle
            self.setproctitle = setproctitle
        except ImportError:
            self.setproctitle = None
        self.name = None
        self.keys = {}
    
    
    def _refresh(self):
        if self.name is None:
            return
        keys = list(self.keys.keys())  # list for python3
        keys.sort()
        process_name = '%s %s' % (self.name, ' '.join(['%s=%s' % (key, self.keys[key]) for key in keys]))
        self._set_process_name(process_name)
    
    
    def _set_process_name(self, process_name):
        if not self.setproctitle:
            return
        self.setproctitle(process_name)
    
    
    def set_raw_title(self, raw_process_title):
        self._set_process_name(raw_process_title)
    
    
    def set_name(self, name):
        self.name = name
        self._refresh()
    
    
    def set_key(self, key, value):
        prev_value = self.keys.get(key, None)
        if prev_value == value:
            return
        self.keys[key] = value
        self._refresh()


_processtitler = None


def get_processtitler():
    global _processtitler
    if _processtitler is None:
        _processtitler = ProcessTitleManager()
    return _processtitler
