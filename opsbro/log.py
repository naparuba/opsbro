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

PY3 = sys.version_info >= (3,)
if PY3:
    unicode = str
    basestring = str

from .misc.colorama import init as init_colorama

# Lasy load to avoid recursive import
string_decode = None


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
        global string_decode
        if string_decode is None:
            from .util import string_decode
            string_decode = string_decode
        if not isinstance(s, basestring):
            s = str(s)
        # Python 2 and 3: good luck for unicode in a terminal.
        # It's a nightmare to manage all of this, if you have a common code
        # that allow to run WITHOUT a terminal, I take it :)
        if PY3:
            s = string_decode(s)
            raw_bytes, consumed = stdout_utf8.encode(s, 'strict')
            if end == '':
                sys.stdout.buffer.write(raw_bytes)
                # stdout_utf8.write(s)
            else:
                sys.stdout.buffer.write(raw_bytes)
                sys.stdout.buffer.write(b'\n')
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
    
    
    def load(self, data_dir, name):
        self.name = name
        self.data_dir = data_dir
        # We can start with a void data dir
        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        self.log_file = codecs.open(os.path.join(self.data_dir, 'daemon.log'), 'ab', encoding="utf-8")
    
    
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
    
    
    def log(self, *args, **kwargs):
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
        f = None
        if part == '':
            if self.log_file is not None:
                self.log_file.write(s)
        else:
            f = self.logs.get(part, None)
            if f is None:
                f = codecs.open(os.path.join(self.data_dir, '%s.log' % part), 'ab', encoding="utf-8")
                self.logs[part] = f
            f.write(s)
            f.flush()
        
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


logger = Logger()


class PartLogger(object):
    def __init__(self, part):
        self.part = part
        self.listener_path = '/tmp/opsbro-follow-%s' % part
    
    
    def debug(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'DEBUG  '
            logger.log(*args, color='magenta', **kwargs)
            return
        logger.debug(*args, **kwargs)
    
    
    def info(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'INFO   '
            logger.log(*args, color='blue', **kwargs)
            return
        logger.info(*args, **kwargs)
    
    
    def warning(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'WARNING'
            logger.log(*args, color='yellow', **kwargs)
            return
        logger.warning(*args, **kwargs)
    
    
    def error(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            kwargs['level'] = 'ERROR  '
            logger.log(*args, color='red', **kwargs)
            return
        logger.error(*args, **kwargs)
    
    
    def log(self, *args, **kwargs):
        kwargs['part'] = kwargs.get('part', self.part)
        if os.path.exists(self.listener_path):
            kwargs['listener'] = self.listener_path
            logger.log(*args, **kwargs)
            return
        logger.log(*args, **kwargs)


# Create logger for a specific part if not already exists
class LoggerFactory(object):
    @classmethod
    def create_logger(cls, part):
        if part in loggers:
            return loggers[part]
        loggers[part] = PartLogger(part)
        return loggers[part]
