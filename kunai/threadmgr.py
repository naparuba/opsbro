import threading
import ctypes
import os
import time
import traceback
import cStringIO
import json
from kunai.httpdaemon import http_export, response
from kunai.log import logger
from kunai.pubsub import pubsub

# this part is doomed for windows portability, will be fun to manage :)
try:
    libc = ctypes.CDLL('libc.so.6')
except Exception:
    libc = None

# TODO: remove psutil and direct look into /proc
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
    except Exception:
        output = cStringIO.StringIO()
        traceback.print_exc(file=output)
        logger.error("Thread %s is exiting on error. Back trace of this error: %s" % (name, output.getvalue()))
        output.close()
        
        if is_essential:
            # Maybe the thread WAS an essential one (like http thread or something like this), if so
            # catch it and close the whole daemon
            logger.error('The thread %s was an essential one, we are stopping the daemon do not be in an invalid state' % name)
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
    
    
    @classmethod
    def __get_thread_entry(cls, name, essential, tid=0):
        return {'thread': None, 'tid': tid, 'name': name, 'essential': essential, 'user_time': -1, 'system_time': -1}
    
    
    def create_and_launch(self, f, args=(), name='', essential=False):
        # If no name, try to give a name even a raw one, to help debug
        if not name:
            name = '(unamed thread:%s)' % f.__name__
        
        d = self.__get_thread_entry(name, essential)
        
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
        @http_export('/threads/', protected=True)
        @http_export('/threads', protected=True)
        def GET_threads():
            response.content_type = 'application/json'
            # Look at CPU usage for threads if we have access to this
            perfs = {}
            our_process = None
            if psutil:
                # NOTE: os.getpid() need by old psutil versions
                our_process = psutil.Process(os.getpid())
                our_threads = our_process.get_threads()
                for thr in our_threads:
                    t_id = thr.id
                    user_time = thr.user_time
                    system_time = thr.system_time
                    perfs[t_id] = {'user_time': user_time, 'system_time': system_time}
            res = {'threads': [], 'process': None, 'age': 0}
            # copy all threads as we will add the main process too
            threads = self.all_threads[:]
            main_thread = self.__get_thread_entry('[Agent] Main thread', True, tid=os.getpid())  # our main thread pid is the process pid
            threads.append(main_thread)
            
            main_process = self.__get_thread_entry('[Agent] Main Process', True, tid=os.getpid())  # our process, to allow to get user/system times
            res['process'] = main_process
            if our_process:
                v = our_process.get_cpu_times()
                main_process['user_time'] = v.user
                main_process['system_time'] = v.system
                res['age'] = time.time() - our_process.create_time
            
            props = ['name', 'tid', 'essential', 'user_time', 'system_time']  # only copy jsonifiable objects
            for d in threads:
                nd = {}
                for prop in props:
                    nd[prop] = d[prop]
                # Try to set perf into it
                t_id = d['tid']
                if t_id in perfs:
                    _perf = perfs[t_id]
                    nd['user_time'] = _perf['user_time']
                    nd['system_time'] = _perf['system_time']
                res['threads'].append(nd)
            # and also our process if possible
            
            return json.dumps(res)


threader = ThreadMgr()
