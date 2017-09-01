import os
import sys
import signal
import locale

# On unix, try to raise system resources to the max (unlimited if possible)
try:
    import resource
except ImportError:
    resource = None

from opsbro.cluster import Cluster
from opsbro.log import cprint, logger
from opsbro.gossip import gossiper

REDIRECT_TO = getattr(os, "devnull", "/dev/null")


# Main class for launching the daemon
class Launcher(object):
    def __init__(self, lock_path='', debug_path='', cfg_dir=''):
        self.lock_path = lock_path
        self.debug_path = debug_path
        self.cfg_dir = cfg_dir
        
        # on windows, skip locale globaly
        if os.name == 'nt':
            locale.setlocale(locale.LC_ALL, 'C')
    
    
    def change_to_workdir(self):
        if os.path.exists('/tmp'):
            try:
                os.chdir('/tmp')
            except Exception, e:
                raise Exception('Invalid working directory /tmp')
    
    
    def unlink(self):
        logger.info("Unlinking lock file %s" % self.lock_path)
        try:
            os.unlink(self.lock_path)
        except Exception, e:
            logger.error("Got an error unlinking our pidfile: %s" % (e))
    
    
    def open_pidfile(self, write=False):
        try:
            p = os.path.abspath(self.lock_path)
            logger.debug("Opening pid file: %s" % p)
            # Windows do not manage the rw+ mode, so we must open in read mode first, then reopen it write mode...
            if not write and os.path.exists(p):
                self.fpid = open(p, 'r+')
            else:  # If it doesn't exist too, we create it as void
                self.fpid = open(p, 'w+')
        except Exception as err:
            raise Exception('Cannot open pid file: %s' % err)
    
    
    # Check (in pidfile) if there isn't already a daemon running. If yes and do_replace: kill it.
    # Keep in self.fpid the File object to the pidfile. Will be used by writepid.
    def check_parallel_run(self):
        # TODO: other daemon run on nt
        if os.name == 'nt':
            logger.warning("The parallel daemon check is not available on nt")
            return
        
        # First open the pid file in open mode
        self.open_pidfile()
        try:
            buf = self.fpid.readline().strip(' \r\n')
            if not buf:  # pid file was void, cool
                return
            pid = int(buf)
        except Exception as err:
            logger.info("Stale pidfile exists at %s (%s). Reusing it." % (err, self.lock_path))
            return
        
        try:
            os.kill(pid, 0)
        except Exception as err:  # consider any exception as a stale pidfile.
            # this includes :
            #  * PermissionError when a process with same pid exists but is executed by another user.
            #  * ProcessLookupError: [Errno 3] No such process.
            logger.info("Stale pidfile exists (%s), Reusing it." % err)
            return
        
        logger.error("Valid previous daemon exists (pid=%s) Exiting." % pid)
        raise SystemExit(2)
    
    
    def write_pid(self, pid=None):
        if pid is None:
            pid = os.getpid()
        self.fpid.seek(0)
        self.fpid.truncate()
        self.fpid.write("%d" % pid)
        self.fpid.close()
        del self.fpid  # no longer needed
    
    
    # Go in "daemon" mode: redirect stdout/err,
    # chdir, umask, fork-setsid-fork-writepid
    def daemonize(self):
        logger.debug("Redirecting stdout and stderr as necessary..")
        if self.debug_path:
            fdtemp = os.open(self.debug_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        else:
            fdtemp = os.open(REDIRECT_TO, os.O_RDWR)
        
        os.dup2(fdtemp, 1)  # standard output (1)
        os.dup2(fdtemp, 2)  # standard error (2)
        
        # Now the fork/setsid/fork..
        try:
            pid = os.fork()
        except OSError, e:
            s = "%s [%d]" % (e.strerror, e.errno)
            logger.error(s)
            raise Exception, s
        
        if pid != 0:
            # In the father: we check if our child exit correctly
            # it has to write the pid of our future little child..
            def do_exit(sig, frame):
                logger.error("Timeout waiting child while it should have quickly returned ; something weird happened")
                os.kill(pid, 9)
                sys.exit(2)
            
            
            # wait the child process to check its return status:
            signal.signal(signal.SIGALRM, do_exit)
            signal.alarm(3)  # forking & writing a pid in a file should be rather quick..
            # if it's not then something wrong can already be on the way so let's wait max 3 secs here.
            pid, status = os.waitpid(pid, 0)
            if status != 0:
                logger.error("Something weird happened with/during second fork: status=", status)
                os._exit(2)
            # In all case we will have to return
            os._exit(0)
        
        # halfway to daemonize..
        os.setsid()
        try:
            pid = os.fork()
        except OSError, e:
            raise Exception, "%s [%d]" % (e.strerror, e.errno)
        if pid != 0:
            # we are the last step and the real daemon is actually correctly created at least.
            # we have still the last responsibility to write the pid of the daemon itself.
            self.write_pid(pid)
            os._exit(0)  # <-- this was the son, the real daemon is the son-son
        
        self.fpid.close()
        del self.fpid
        self.pid = os.getpid()
        logger.info("Daemonization done: pid=%d" % self.pid)
    
    
    def do_daemon_init_and_start(self, is_daemon=False):
        self.change_to_workdir()
        self.check_parallel_run()
        
        # Force the debug level if the daemon is said to start with such level
        if self.debug_path:
            logger.setLevel('DEBUG')
        
        # If daemon fork() until we reach the final step
        if is_daemon:
            self.daemonize()
        else:
            if os.name != 'nt':
                self.write_pid()
                # Here only the son-son reach this part :)
        
        # Now we are started, try to raise system limits to the maximum allowed
        self.find_and_set_higer_system_limits()
    
    
    def find_and_set_higer_system_limit(self, res, res_name):
        # first try to get the system limit, if already unlimited (-1) then we are good :)
        soft, hard = resource.getrlimit(res)
        if soft == -1 and hard == -1:
            logger.info('System resource %s is already unlimited: (soft:%s/hard:%s)' % (res_name, soft, hard))
            return
        # Ok not unlimited, maybe we can set unlimited?
        try:
            resource.setrlimit(res, (-1, -1))
            is_unlimited = True
        except ValueError:
            is_unlimited = False
        if is_unlimited:
            logger.info('System resource %s was set to unlimited' % (res_name))
            return
        # Ok maybe we cannot set unlimited, but we can try to increase it as much as we can
        can_still_increase = True
        v = hard
        if hard == -1:
            v = soft
        while can_still_increase:
            v *= 2
            try:
                logger.debug('Try to increase system limit %s to %s/%s' % (res_name, v, v))
                resource.setrlimit(res, (v, v))
            except ValueError:
                # We did find the max
                can_still_increase = False
        logger.info('System limit %s is set to maximum available: %s/%s' % (res_name, v, v))
    
    
    def find_and_set_higer_system_limits(self):
        if not resource:
            logger.info('System resource package is not available, cannot increase system limits')
            return
        for (res, res_name) in [(resource.RLIMIT_NPROC, 'number of process/threads'), (resource.RLIMIT_NOFILE, 'number of open files')]:
            self.find_and_set_higer_system_limit(res, res_name)
    
    
    # Main locking function, will LOCK here until the daemon is dead/killed/whatever
    def main(self):
        c = Cluster(cfg_dir=self.cfg_dir)
        cprint('Linking services and checks', color='green')
        cprint('Launching listeners', color='green')
        c.launch_listeners()
        cprint('Joining seeds nodes', color='green')
        c.join()
        cprint('Starting check, collector and generator threads', color='green')
        c.launch_check_thread()
        c.launch_collector_thread()
        c.launch_generator_thread()
        c.launch_detector_thread()
        c.launch_installor_thread()
        
        if 'kv' in gossiper.groups:
            c.launch_replication_backlog_thread()
            c.launch_replication_first_sync_thread()
        c.start_ts_listener()
        
        # Blocking function here
        c.main()
