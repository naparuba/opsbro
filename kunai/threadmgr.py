import threading
import ctypes
import os
import traceback
import cStringIO
import json
from kunai.httpdaemon import route, response, protected
from kunai.log import logger
from kunai.pubsub import pubsub

# this part is doomed for windows portability, will be fun to manage :)
try:
    libc = ctypes.CDLL('libc.so.6')
except Exception:
    libc = None

try:
    import psutil
except ImportError:
    psutil = None


# The f() wrapper
def w(d, f, name, is_essential, args):
    import cStringIO
    import traceback
    import time
    from kunai.log import logger
    from kunai.pubsub import pubsub
    
    tid = 0
    if libc:
        tid = libc.syscall(186)  # get the threadid when you are in it :)
    logger.debug('THREAD launch (%s) with thread id (%d)' % (name, tid))
    # Set in our entry object
    d['tid'] = tid
    try:
        f(*args)
    except Exception, exp:
        output = cStringIO.StringIO()
        traceback.print_exc(file=output)
        logger.error("Thread %s is exiting on error. Back trace of this error: %s" % (name, output.getvalue()))
        output.close()
        
        if is_essential:
            # Maybe the thread WAS an essential one (like http thread or something like this), if so
            # catch it and close the whole daemon
            logger.error(
                'The thread %s was an essential one, we are stopping the daemon do not be in an invalid state' % name)
            pubsub.pub('interrupt')
            
            # Create a daemon thread with our wrapper function that will manage initial logging


class ThreadMgr(object):
    def __init__(self):
        self.all_threads = []
        self.export_http()
    
    
    def check_alives(self):
        self.all_threads = [d for d in self.all_threads if d['thread'].is_alive()]
    
    
    def get_info(self):
        return {'nb_threads': len(self.all_threads)}
    
    
    def create_and_launch(self, f, args=(), name='unamed-thread', essential=False):
        d = {'thread': None, 'tid': 0, 'name': name, 'essential': essential, 'user_time': -1, 'system_time': -1}
        
        # and exception catchs
        t = threading.Thread(None, target=w, name=name, args=(d, f, name, essential, args))
        t.daemon = True
        t.start()
        # Save this thread object
        d['thread'] = t
        self.all_threads.append(d)
        return t
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        @route('/threads/')
        @route('/threads')
        # @protected()
        def GET_threads():
            response.content_type = 'application/json'
            # Look at CPU usage for threads if we have access to this
            perfs = {}
            if psutil:
                # NOTE: os.getpid() need by old psutil versions
                our_process = psutil.Process(os.getpid())
                our_threads = our_process.get_threads()
                for thr in our_threads:
                    t_id = thr.id
                    user_time = thr.user_time
                    system_time = thr.system_time
                    perfs[t_id] = {'user_time': user_time, 'system_time': system_time}
            res = []
            props = ['name', 'tid', 'essential', 'user_time', 'system_time']  # only copy jsonifiable objects
            for d in self.all_threads:
                nd = {}
                for prop in props:
                    nd[prop] = d[prop]
                # Try to set perf into it
                t_id = d['tid']
                if t_id in perfs:
                    _perf = perfs[t_id]
                    nd['user_time'] = _perf['user_time']
                    nd['system_time'] = _perf['system_time']
                res.append(nd)
            
            return json.dumps(res)


threader = ThreadMgr()
