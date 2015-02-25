import threading
import ctypes
import traceback
import cStringIO

from kunai.log import logger
from kunai.pubsub import pubsub

# this part is doomed for windows portability, will be fun to manage :)
try:
    libc = ctypes.CDLL('libc.so.6')
except Exception:
    libc = None



class ThreadMgr(object):
    def __init__(self):
        self.all_threads = []


    def check_alives(self):
        self.all_threads = [t for t in self.all_threads if t.is_alive()]                


    def get_info(self):
        return {'nb_threads' : len(self.all_threads)}
    

    def create_and_launch(self, f, args=(), name='unamed-thread', essential=False):
        def w(is_essential):
            tid = 0
            if libc:
                tid = libc.syscall(186) # get the threadid when you are in it :)
            logger.info('THREAD launch (%s) with thread id (%d)' % (name, tid))
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
                    logger.error('The thread %s was an essential one, we are stopping the daemon do not be in an invalid state' % name)
                    pubsub.pub('interrupt')                

        # Create a daemon thread with our wrapper function that will manage initial logging
        # and exception catchs
        t = threading.Thread(None, target=w, name=name, args=(essential,))
        t.daemon = True
        t.start()
        self.all_threads.append(t)
        return t


threader = ThreadMgr()
