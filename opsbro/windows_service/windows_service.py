import win32service
import win32serviceutil
import locale
import win32event
import sys
import traceback

from opsbro.launcher import Launcher
from opsbro.threadmgr import threader
from opsbro.stop import stopper
from opsbro.log import LoggerFactory

logger_crash = LoggerFactory.create_logger('crash')

def LOG(s):
    with open(r'c:\opsbro.txt', 'a') as f:
        f.write('%s\n' % s)
    

LOG('IMPORT')

class Service(win32serviceutil.ServiceFramework):
    _svc_name_ = "OpsBro"
    _svc_display_name_ = "OpsBro"
    _svc_description_ = "OpsBro is a monitoring and discovery agent."
    
    
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
            stopper.do_stop('Stop from windows service')
    
    
    def destroy_stdout_stderr(self):
        class NullWriter(object):
            is_null_write = True
            
            
            def write(self, value):
                pass
        
        sys.stdout = sys.stderr = NullWriter()
    
    
    # Before launch the main/start, we need to have a stopper thread
    def _before_start_callback(self):
        threader.create_and_launch(self.__check_for_hWaitStop, (), name='Windows service stopper', essential=True, part='agent')
    
    
    def SvcDoRun(self):
        try:
            LOG('SvcDoRun')
            import servicemanager
            servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ''))
            servicemanager.LogInfoMsg("OpsBro Start")

            # Set as english
            locale.setlocale(locale.LC_ALL, 'English_Australia.1252')
            
            # under service, stdout and stderr are not available
            # TODO: enable debug mode?
            self.destroy_stdout_stderr()
            LOG('BEFORE CLI')
            # simulate CLI startup with config parsing
            from opsbro.log import cprint, logger, is_tty
            from opsbro.cli import CLICommander, save_current_binary
            from opsbro.yamlmgr import yamler
            
            with open('c:\\opsbro\\etc\\agent.yml', 'r') as f:
                buf = f.read()
                CONFIG = yamler.loads(buf)

            LOG('CONF LOADED')
            
            # Load config
            CLI = CLICommander(CONFIG, None)
            
            LOG('CLI LOADED')
            l = Launcher(cfg_dir='c:\\opsbro\\etc')
            LOG('LAUNCHER created, launching init & main')
            # Note: before launch the start/main, we need to start a stopper thread (on the main process)
            l.do_daemon_init_and_start(is_daemon=False, before_start_callback=self._before_start_callback)
            LOG('LAUNCHER init')
            # called when we're being shut down
        except Exception:
            err = traceback.format_exc()
            LOG('CRASH: %s' % err)
            logger_crash.error(err)
            raise
    
    
    def SvcStop(self):
        import servicemanager
        # tell windows SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        servicemanager.LogInfoMsg("OpsBro Start")
        # launch the stop event
        win32event.SetEvent(self.hWaitStop)


def ctrlHandler(ctrlType):
    return True

# if __name__ == '__main__':
#    win32api.SetConsoleCtrlHandler(ctrlHandler, True)
#    win32serviceutil.HandleCommandLine(Service)
