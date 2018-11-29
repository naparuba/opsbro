#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys
import time
import datetime
import logging
import json
import codecs
import shutil
from glob import glob
from threading import Lock as ThreadLock
from multiprocessing.sharedctypes import Value
from ctypes import c_int

PY3 = sys.version_info >= (3,)
if PY3:
    unicode = str
    basestring = str

from .misc.colorama import init as init_colorama

# Lasy load to avoid recursive import
string_decode = None
bytes_to_unicode = None

# Keep 7 days of logs
LOG_ROTATION_KEEP = 7 + 1


def is_tty():
    # TODO: what about windows? how to have beautiful & Windows?
    # on windows, we don't know how to have cool output
    if os.name == 'nt':
        # We must consider the classic CMD as a no tty, as it's just too limited
        if os.environ.get('ANSICON', '') == '':
            return False
    
    # Look if we are in a tty or not
    if hasattr(sys.stdout, 'isatty'):
        return sys.stdout.isatty()
    return False


if is_tty():
    # Try to load the terminal color. Won't work under python 2.4
    try:
        from .misc.termcolor import cprint, sprintf
        
        # init the colorama hook, for windows print
        # will do nothing for other than windows
        init_colorama()
    except (SyntaxError, ImportError) as exp:
        # Outch can't import a cprint, do a simple print
        def cprint(s, color='', on_color='', end='\n'):
            print(s, end=end)
        
        
        # Also overwrite sprintf
        def sprintf(s, color='', end=''):
            return s



# Ok it's a daemon mode, if so, just print
else:
    # Protect sys.stdout write for utf8 outputs
    import codecs
    
    stdout_utf8 = codecs.getwriter("utf-8")(sys.stdout)
    
    
    # stdout_utf8.errors = 'ignore'
    
    def cprint(s, color='', on_color='', end='\n'):
        global string_decode, bytes_to_unicode
        if os.name == 'nt' and hasattr(sys.stdout, 'is_null_write'):  # maybe we are in a windows service, so skip printing
            return
        if string_decode is None:
            from .util import string_decode
            string_decode = string_decode
        if bytes_to_unicode is None:
            from .util import bytes_to_unicode
            bytes_to_unicode = bytes_to_unicode
        if not isinstance(s, basestring):
            s = str(s)
        # Python 2 and 3: good luck for unicode in a terminal.
        # It's a nightmare to manage all of this, if you have a common code
        # that allow to run WITHOUT a terminal, I take it :)
        if PY3:
            s = string_decode(s)
            raw_bytes, consumed = stdout_utf8.encode(s, 'strict')
            # We have 2 cases:
            # * (default) sys.stdout is a real tty we did hook
            # * (on test case by nose) was changed by a io.Stdout that do not have .buffer
            end_line = b'\n'
            if hasattr(sys.stdout, 'buffer'):
                write_into = sys.stdout.buffer
            else:
                write_into = sys.stdout
                raw_bytes = bytes_to_unicode(raw_bytes)  # ioString do not like bytes
                end_line = '\n'
            if end == '':
                write_into.write(raw_bytes)
            else:
                write_into.write(raw_bytes)
                write_into.write(end_line)
        else:  # PY2
            if end == '':
                stdout_utf8.write(s)
            else:
                stdout_utf8.write(s)
                stdout_utf8.write('\n')
    
    
    def sprintf(s, color='', end=''):
        return s


def get_unicode_string(s):
    if isinstance(s, str) and not PY3:
        return unicode(s, 'utf8', errors='ignore')
    return unicode(s)


loggers = {}


class Logger(object):
    def __init__(self):
        self.data_dir = ''
        self.log_file = None
        self.name = ''
        self.logs = {}
        self.registered_parts = {}
        self.level = logging.INFO
        self.is_force_level = False  # is the currently level is a force one or not (force by API or by CLI args for example)
        self.linkify_methods()
        
        # We will keep last 20 errors
        self.last_errors_stack_size = 20
        self.last_errors_stack = {'DEBUG': [], 'WARNING': [], 'INFO': [], 'ERROR': []}
        
        self.last_date_print_time = 0
        self.last_date_print_value = ''
        
        self.last_rotation_day = Value(c_int, 0)  # shared epoch of the last time we did rotate, round by 86400
        
        # Log will be protected by a lock (for rotating and such things)
        # WARNING the lock is link to a pid, if used on a sub process it can fail because
        # the master process can have aquire() it and so will never unset it in your new process
        self.log_lock = None
        self.current_lock_pid = os.getpid()
    
    
    # ~Get (NOT aquire) current lock, but beware: if we did change process, recreate it
    def _get_lock(self):
        cur_pid = os.getpid()
        if self.log_lock is None or self.current_lock_pid != cur_pid:
            self.log_lock = ThreadLock()
        return self.log_lock
    
    
    # A code module register it's
    def register_part(self, pname):
        # By default we show it if the global level is ok with this
        self.registered_parts[pname] = {'enabled': True}
    
    
    def linkify_methods(self):
        methods = {'DEBUG': self.do_debug, 'WARNING': self.do_warning, 'INFO': self.do_info, 'ERROR': self.do_error}
        for (s, m) in methods.items():
            level = getattr(logging, s)
            # If the level is enough, link it
            if level >= self.level:
                setattr(self, s.lower(), m)
            else:
                setattr(self, s.lower(), self.do_null)
    
    
    def _get_log_file_path(self, fname):
        return os.path.join(self.data_dir, fname)
    
    
    def _get_log_open(self, fname):
        return codecs.open(self._get_log_file_path(fname), 'ab', encoding="utf-8")
    
    
    def load(self, data_dir, name):
        self.name = name
        self.data_dir = data_dir
        # We can start with a void data dir
        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        self.log_file = self._get_log_open('daemon.log')
    
    
    # If a level is set to force, a not foce setting is not taken
    # if a level we set by force before, and this call is not a force one, skip this one
    def setLevel(self, s, force=False):
        if not force and self.is_force_level:
            return
        if force:
            self.is_force_level = True
        try:
            level = getattr(logging, s.upper())
            if not isinstance(level, int):
                raise AttributeError
            self.level = level
        except AttributeError:
            self.error('Invalid logging level configuration %s' % s)
            return
        
        self.linkify_methods()
    
    
    def get_errors(self):
        return self.last_errors_stack
    
    
    def __get_time_display(self):
        now = int(time.time())
        # Cache hit or not?
        if now == self.last_date_print_time:
            return self.last_date_print_value
        # save it
        # NOTE: I know there is a small chance of thread race issue, but he, I don't fucking care about a 1s issue delay, deal with it.
        self.last_date_print_value = datetime.datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')
        return self.last_date_print_value
    
    
    def _get_day_string_for_log(self, epoch):
        return datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d')
    
    
    # We will find all .log file and rotate them to the yesterday day
    # NOTe: if not running for several days, this will make past log from yesterday, I know
    # and it's ok
    def _check_log_rotation(self):
        now = int(time.time())
        current_day_nb, current_day_offset = divmod(now, 86400)
        if current_day_nb == self.last_rotation_day.value:
            return
        
        # Maybe we are just starting, if so, do not rotate, no luck for old files and
        # was not running at midnight
        if current_day_nb == 0:
            self.last_rotation_day.value = current_day_nb
            return
        
        self.last_rotation_day.value = current_day_nb  # warn ourselve but aso other sub process
        
        # As we will rotate them, we need to close all files
        # note: clean all logs entries, will be reopen when need
        for (part, f) in self.logs.items():
            f.close()
        self.logs.clear()
        self.log_file.close()
        self.log_file = None
        
        # ok need to rotate
        in_yesterday = (current_day_nb * 86400) - 1
        yesterday_string = self._get_day_string_for_log(in_yesterday)
        
        # At which time the file is too old to be kept?
        too_old_limit = (current_day_nb * 86400) - (LOG_ROTATION_KEEP * 86400)  # today minus - days
        
        all_log_files = glob(os.path.join(self.data_dir, '*.log'))
        for file_path in all_log_files:
            # Maybe the file is too old, if so, delete it
            if os.stat(file_path).st_mtime < too_old_limit:
                try:
                    os.unlink(file_path)
                except OSError:  # oups, cannot remove, but we are the log, cannot log this...
                    pass
                continue
            self._do_rotate_one_log(file_path, yesterday_string)
    
    
    @staticmethod
    def _do_rotate_one_log(base_full_path, yesterday_string):
        if os.path.exists(base_full_path):
            shutil.move(base_full_path, base_full_path + '.' + yesterday_string)
    
    
    def _get_log_file_and_rotate_it_if_need(self, part):
        self._check_log_rotation()
        
        # core daemon.log
        if part == '':
            if self.log_file is None:  # was rotated
                self.log_file = self._get_log_open('daemon.log')
            return self.log_file
        
        # classic part log
        f = self.logs.get(part, None)
        if f is None:  # was rotated or maybe rotated
            log_name = '%s.log' % part
            f = self._get_log_open(log_name)
            self.logs[part] = f
        return self.logs[part]
    
    
    def log(self, *args, **kwargs):
        # We must protect logs against thread access, and even sub-process ones
        with self._get_lock():
            part = kwargs.get('part', '')
            s_part = '' if not part else '[%s]' % part.upper()
            
            d_display = self.__get_time_display()
            s = '[%s][%s][%s] %s: %s' % (d_display, kwargs.get('level', 'UNSET  '), self.name, s_part, u' '.join([get_unicode_string(s) for s in args]))
            
            # Sometime we want a log output, but not in the stdout
            if kwargs.get('do_print', True):
                if 'color' in kwargs:
                    cprint(s, color=kwargs['color'])
                else:
                    print(s)
            stack = kwargs.get('stack', False)
            
            # Not a perf problems as it's just for errors and a limited size
            if stack:
                self.last_errors_stack[stack].append(s)
                # And keep only the last 20 ones for example
                self.last_errors_stack[stack] = self.last_errors_stack[stack][-self.last_errors_stack_size:]
            
            # if no data_dir, we cannot save anything...
            if self.data_dir == '':
                return
            s = s + '\n'
            
            # Now get the log file and write into it
            # NOTE: if need, will rotate all files
            f = self._get_log_file_and_rotate_it_if_need(part)
            f.write(s)
            f.flush()
            
            # Now update the log listener if exis
            listener = kwargs.get('listener', '')
            if listener and hasattr(os, 'O_NONBLOCK') and f is not None:  # no named pipe on windows
                try:
                    fd = os.open(listener, os.O_WRONLY | os.O_NONBLOCK)
                    os.write(fd, s)
                    os.close(fd)
                except Exception as exp:  # maybe the path did just disapear
                    s = "ERROR LISTERNER %s" % exp
                    f.write(s)
    
    
    def do_debug(self, *args, **kwargs):
        self.log(*args, level='DEBUG', color='magenta', **kwargs)
    
    
    def do_info(self, *args, **kwargs):
        self.log(*args, level='INFO', color='blue', **kwargs)
    
    
    def do_warning(self, *args, **kwargs):
        self.log(*args, level='WARNING', color='yellow', stack='WARNING', **kwargs)
    
    
    def do_error(self, *args, **kwargs):
        self.log(*args, level='ERROR', color='red', stack='ERROR', **kwargs)
    
    
    def do_null(self, *args, **kwargs):
        pass
    
    
    def export_http(self):
        from .httpdaemon import http_export, response
        @http_export('/log/parts/')
        def list_parts():
            response.content_type = 'application/json'
            return json.dumps(loggers.keys())


core_logger = Logger()


class PartLogger(object):
    def __init__(self, part):
        self.part = part
        self.listener_path = '/tmp/opsbro-follow-%s' % part
    
    
    def debug(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'DEBUG  '
            core_logger.log(*args, color='magenta', **kwargs)
            return
        core_logger.debug(*args, **kwargs)
    
    
    def info(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'INFO   '
            core_logger.log(*args, color='blue', **kwargs)
            return
        core_logger.info(*args, **kwargs)
    
    
    def warning(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'WARNING'
            core_logger.log(*args, color='yellow', **kwargs)
            return
        core_logger.warning(*args, **kwargs)
    
    
    def error(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'ERROR  '
            core_logger.log(*args, color='red', **kwargs)
            return
        core_logger.error(*args, **kwargs)
    
    
    def log(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            core_logger.log(*args, **kwargs)
            return
        core_logger.log(*args, **kwargs)
    
    
    def setLevel(self, s, force=False):
        core_logger.setLevel(s, force=force)
    
    
    def load(self, data_dir, name):
        core_logger.load(data_dir, name)


# Create logger for a specific part if not already exists
class LoggerFactory(object):
    @classmethod
    def create_logger(cls, part):
        if part in loggers:
            return loggers[part]
        loggers[part] = PartLogger(part)
        return loggers[part]


logger = LoggerFactory.create_logger('daemon')
