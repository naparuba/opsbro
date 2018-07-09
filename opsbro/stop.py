import sys
import os
import time

t0 = time.time()

MAX_DUMP_STOP_LEVEL = 10


class Stopper(object):
    def __init__(self):
        self._interrupted = False
    
    
    def do_stop(self, reason):
        from .log import logger
        level = 0
        callers = []
        while True:
            level += 1
            if level > MAX_DUMP_STOP_LEVEL:
                break
            try:
                _frame = sys._getframe(level)
                f_name = _frame.f_code.co_name
                f_file = _frame.f_code.co_filename
                f_line = _frame.f_lineno
                callers.append('%s - (%s, line %s)' % (f_name, os.path.basename(f_file), f_line))
            except ValueError:  # no more levels
                break
            except Exception as exp:
                callers += (' (cannot get caller name: %d: %s)' % (level, exp))
                break
        if len(callers) == 0:
            callers.append('unknown function')
        logger.info('The daemon is asking to stop : %s' % (reason))
        logger.debug('The daemon is asking to stop by the function: [ %s ] because of %s' % (' -> '.join(callers), reason))
        self._interrupted = True
    
    
    def is_stop(self):
        return self._interrupted


stopper = Stopper()
