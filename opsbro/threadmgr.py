import threading

try:
    import ctypes
except ImportError:  # on python static build for example
    ctypes = None
import sys
import os
import time
import traceback
import cStringIO
import json
from opsbro.httpdaemon import http_export, response
from opsbro.log import logger
from opsbro.pubsub import pubsub

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

# Hook threading to allow thread renaming
if sys.platform.startswith("win"):
    def namer():
        # If no ctypes, like in a static python build: exit
        try:
            import ctypes
        except ImportError:
            return
        import threading
        import time
        from ctypes import wintypes
        
        class THREADNAME_INFO(ctypes.Structure):
            _pack_ = 8
            _fields_ = [
                ("dwType", wintypes.DWORD),
                ("szName", wintypes.LPCSTR),
                ("dwThreadID", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
            ]
            
            
            def __init__(self):
                self.dwType = 0x1000
                self.dwFlags = 0
        
        def debugChecker():
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            RaiseException = kernel32.RaiseException
            RaiseException.argtypes = [
                wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                ctypes.c_void_p]
            RaiseException.restype = None
            
            IsDebuggerPresent = kernel32.IsDebuggerPresent
            IsDebuggerPresent.argtypes = []
            IsDebuggerPresent.restype = wintypes.BOOL
            MS_VC_EXCEPTION = 0x406D1388
            info = THREADNAME_INFO()
            while True:
                time.sleep(1)
                if IsDebuggerPresent():
                    for thread in threading.enumerate():
                        if thread.ident is None:
                            continue  # not started
                        if hasattr(threading, "_MainThread"):
                            if isinstance(thread, threading._MainThread):
                                continue  # don't name the main thread
                        info.szName = "%s (Python)" % (thread.name,)
                        info.dwThreadID = thread.ident
                        try:
                            RaiseException(MS_VC_EXCEPTION, 0,
                                           ctypes.sizeof(info) / ctypes.sizeof(
                                               ctypes.c_void_p),
                                           ctypes.addressof(info))
                        except:
                            pass
        
        
        dt = threading.Thread(target=debugChecker,
                              name="MSVC debugging support thread")
        dt.daemon = True
        dt.start()
    
    
    namer()
    del namer
elif sys.platform.startswith("linux"):
    def namer():
        # Return if python was build without ctypes (like in a static build)
        try:
            import ctypes
            import ctypes.util
        except ImportError:
            return
        import threading
        libpthread_path = ctypes.util.find_library("pthread")
        if not libpthread_path:
            return
        libpthread = ctypes.CDLL(libpthread_path)
        if not hasattr(libpthread, "pthread_setname_np"):
            return
        pthread_setname_np = libpthread.pthread_setname_np
        pthread_setname_np.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        pthread_setname_np.restype = ctypes.c_int
        
        orig_setter = threading.Thread.__setattr__
        
        
        def attr_setter(self, name, value):
            orig_setter(self, name, value)
            if name == "name":
                ident = getattr(self, "ident", None)
                if ident:
                    try:
                        pthread_setname_np(ident, str(value[:15]))
                    except:
                        pass  # Don't care about failure to set name
        
        
        threading.Thread.__setattr__ = attr_setter
        
        # set the thread name to itself to trigger the new logic
        for thread in threading.enumerate():
            if thread.name:
                if hasattr(threading, "_MainThread"):
                    if isinstance(thread, threading._MainThread):
                        continue  # don't name the main thread
                thread.name = thread.name
    
    
    namer()
    del namer


# The f() wrapper
def w(d, f, name, is_essential, args):
    import cStringIO
    import traceback
    import time
    from opsbro.log import logger
    from opsbro.pubsub import pubsub
    
    tid = 0
    if libc:
        tid = libc.syscall(186)  # get the threadid when you are in it :)
    logger.debug('THREAD launch (%s) with thread id (%d)' % (name, tid))
    # Set in our entry object
    d['tid'] = tid
    # Change the system name of the thread, if possible
    d['thread'].name = name
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
    def __get_thread_entry(cls, name, essential, part='', tid=0):
        return {'thread': None, 'tid': tid, 'name': name, 'essential': essential, 'user_time': -1, 'system_time': -1, 'part': part}
    
    
    def create_and_launch(self, f, args=(), name='', essential=False, part=''):
        # If no name, try to give a name even a raw one, to help debug
        if not name:
            name = '(unamed thread:%s)' % f.__name__
        
        d = self.__get_thread_entry(name, essential, part=part)
        
        # and exception catchs
        t = threading.Thread(None, target=w, name=name, args=(d, f, name, essential, args))
        t.daemon = True
        d['thread'] = t
        t.start()
        # Save this thread object
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
            main_thread = self.__get_thread_entry('Main thread', True, tid=os.getpid(), part='agent')  # our main thread pid is the process pid
            threads.append(main_thread)
            
            main_process = self.__get_thread_entry('Main Process', True, tid=os.getpid(), part='agent')  # our process, to allow to get user/system times
            res['process'] = main_process
            if our_process:
                v = our_process.get_cpu_times()
                main_process['user_time'] = v.user
                main_process['system_time'] = v.system
                res['age'] = time.time() - our_process.create_time
            
            props = ['name', 'tid', 'essential', 'user_time', 'system_time', 'part']  # only copy jsonifiable objects
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
