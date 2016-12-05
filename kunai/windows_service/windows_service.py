import win32service
import win32serviceutil
import locale
import win32event
import sys

from kunai.pubsub import pubsub
from kunai.launcher import Launcher
from kunai.threadmgr import threader


class Service(win32serviceutil.ServiceFramework):
    _svc_name_ = "Kunai"
    _svc_display_name_ = "Kunai"
    _svc_description_ = "Kunai is a monitoring and discovery agent."
    
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # create an event to listen for stop requests on
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        # core logic of the service
    
    
    def __check_for_hWaitStop(self):
        while True:
            rc = None
            # if the stop event hasn't been fired keep looping
            while rc != win32event.WAIT_OBJECT_0:
                # block for 100ms and listen for a stop event
                rc = win32event.WaitForSingleObject(self.hWaitStop, 100)
            # ok here we stop, warn the other parts about it
            pubsub.pub('interrupt')
    
    
    def destroy_stdout_stderr(self):
        class NullWriter(object):
            def write(self, value): pass
        
        sys.stdout = sys.stderr = NullWriter()
    
    
    def SvcDoRun(self):
        import servicemanager

        # Set as english
        locale.setlocale(locale.LC_ALL, '')
        
        # under service, stdout and stderr are not available
        # TODO: enable debug mode?
        self.destroy_stdout_stderr()
        l = Launcher(cfg_dir='c:\\kunai\\etc')
        l.do_daemon_init_and_start(is_daemon=False)
        # Start the stopper threads
        threader.create_and_launch(self.__check_for_hWaitStop, (), name='windows-service-stopper', essential=True)
        # Here only the last son reach this
        l.main()
        # called when we're being shut down
    
    
    def SvcStop(self):
        # tell windows SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # launch the stop event
        win32event.SetEvent(self.hWaitStop)


def ctrlHandler(ctrlType):
    return True


# if __name__ == '__main__':
#    win32api.SetConsoleCtrlHandler(ctrlHandler, True)
#    win32serviceutil.HandleCommandLine(Service)
