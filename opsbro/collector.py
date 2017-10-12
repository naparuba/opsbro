import os
import platform
import traceback
import subprocess

from opsbro.log import LoggerFactory
from opsbro.parameters import ParameterBasedType

pythonVersion = platform.python_version_tuple()


class Collector(ParameterBasedType):
    class __metaclass__(type):
        __inheritors__ = set()
        
        
        def __new__(meta, name, bases, dct):
            klass = type.__new__(meta, name, bases, dct)
            # When creating the class, we need to look at the module where it is. It will be create like this (in collectormanager)
            # collector___global___windows___collector_iis ==> level=global  pack_name=windows, collector_name=collector_iis
            from_module = dct['__module__']
            elts = from_module.split('___')
            # Note: the master class Collector will go in this too, but its module won't match the ___ filter
            if len(elts) != 1:
                # Let the klass know it
                klass.pack_level = elts[1]
                klass.pack_name = elts[2]
            
            meta.__inheritors__.add(klass)
            return klass
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    
    def __init__(self):
    
        ParameterBasedType.__init__(self)
        
        # Global logger for this part
        self.logger = LoggerFactory.create_logger('collector.%s.%s' % (self.pack_name, self.__class__.__name__.lower()))
        
        self.pythonVersion = pythonVersion
        self.state = 'pending'
        self.log = ''
        
        self.mysqlConnectionsStore = None
        self.mysqlSlowQueriesStore = None
        self.mysqlVersion = None
        
        self.nginxRequestsStore = None
        self.mongoDBStore = None
        self.apacheTotalAccesses = None
        self.plugins = None
        self.topIndex = 0
        self.os = None
        self.linuxProcFsLocation = None
        
        # The manager all back
        from collectormanager import collectormgr
        self.put_result = collectormgr.put_result
        
    
    # our run did fail, so we must exit in a clean way and keep a log
    # if we can
    # NOTE: we want the error in our log file, but not in the stdout of the daemon
    # to let the stdout errors for real daemon error
    def error(self, txt):
        self.logger.error(txt, do_print=False)
        self.log = txt
    
    
    # Execute a shell command and return the result or '' if there is an error
    def execute_shell(self, cmd):
        # Get output from a command
        self.logger.debug('execute_shell:: %s' % cmd)
        output = ''
        try:
            close_fds = True
            # windows do not manage close fds
            if os.name == 'nt':
                close_fds = False
            proc = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, close_fds=close_fds)
            self.logger.debug('PROC LAUNCHED', proc)
            output, err = proc.communicate()
            self.logger.debug('OUTPUT, ERR', output, err)
            try:
                proc.kill()
            except Exception, e:
                pass
            if err:
                self.logger.error('Error in sub process', err)
        except Exception, exp:
            self.error('Collector [%s] execute command [%s] error: %s' % (self.__class__.__name__.lower(), cmd, traceback.format_exc()))
            return False
        return output
    
    
    # from a dict recursivly build a ts
    # 'bla':{'foo':bar, 'titi': toto} => bla.foo.bar bla.titi.toto
    def create_ts_from_data(self, d, l, s):
        if not isinstance(d, dict):
            if isinstance(d, basestring):  # bad value
                return
            if isinstance(d, float) or isinstance(d, int) or isinstance(d, long):
                # print "FINISH HIM!"
                _t = l[:]
                # _t.append(d)
                _nts = '.'.join(_t)  # ts, d)
                # Keep the metric name and value as precise as possible
                # so we don't have to parse them again
                nts = (_nts.lower(), d)
                s.add(nts)
            return
        # For each key,
        for (k, v) in d.iteritems():
            nl = l[:]  # use a copy to l so it won't be overwriten
            nl.append(k)
            self.create_ts_from_data(v, nl, s)
    
    
    # Virtual method, do your own!
    def launch(self):
        raise NotImplemented()
    
    
    def main(self):
        self.logger.debug('Launching main for %s' % self.__class__)
        # Reset log
        self.log = ''
        try:
            r = self.launch()
        except Exception:
            self.logger.error('Collector %s main error: %s' % (self.__class__.__name__.lower(), traceback.format_exc()))
            self.error(traceback.format_exc())
            # And a void result
            if self.put_result:
                self.put_result(self.__class__.__name__.lower(), False, [], self.log)
            return
        
        s = set()
        self.create_ts_from_data(r, [], s)
        if self.put_result:
            self.put_result(self.__class__.__name__.lower(), r, list(s), self.log)
