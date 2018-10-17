# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import json
import imp
import traceback
import sys
import optparse
import time
import itertools
import subprocess

PY3 = (sys.version_info[0] == 3)
if PY3:
    xrange = range  # note: python 3 do not have xrange

from .configurationmanager import configmgr
from .collectormanager import collectormgr
from .modulemanager import modulemanager
from .packer import packer
from .unixclient import get_json, get_local, get_request_errors
from .httpclient import httper
from .log import cprint, logger, sprintf
from .defaultpaths import DEFAULT_LOG_DIR, DEFAULT_CFG_DIR, DEFAULT_DATA_DIR, DEFAULT_SOCK_PATH
from .info import VERSION
from .cli_display import print_h1, get_terminal_size
from .topic import topiker
from .characters import CHARACTERS
from .misc.lolcat import lolcat
from .cluster import AGENT_STATE_STOPPED
from .now import NOW
from .jsonmgr import jsoner

# Will be populated by the opsbro CLI command
CONFIG = None

CURRENT_BINARY = ''
DEFAULT_INFO_COL_SIZE = 22


# We should save the current opsbro binary used, for debug purpose for example
def save_current_binary(pth):
    global CURRENT_BINARY
    CURRENT_BINARY = pth


def get_current_binary():
    global CURRENT_BINARY
    return CURRENT_BINARY


def get_local_socket():
    return CONFIG.get('socket', DEFAULT_SOCK_PATH)


if os.name != 'nt':
    def get_opsbro_json(uri, timeout=10):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, timeout=timeout)
    
    
    def get_opsbro_local(uri):
        local_socket = get_local_socket()
        return get_local(uri, local_socket)
    
    
    def post_opsbro_json(uri, data, timeout=10):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, params=data, method='POST', timeout=timeout)
    
    
    def put_opsbro_json(uri, data):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, params=data, method='PUT')
    
    
    def delete_opsbro_json(uri):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, method='DELETE')


else:
    def get_opsbro_json(uri, timeout=10):
        r = httper.get('http://127.0.0.1:6770%s' % uri)
        obj = jsoner.loads(r)
        return obj
    
    
    # TODO: catch the real status code?
    def get_opsbro_local(uri):
        r = httper.get('http://127.0.0.1:6770%s' % uri)
        status = 200  # if not, should have send an exception
        text = r
        return (status, text)
    
    
    def post_opsbro_json(uri, data, timeout=10):
        return get_json(uri, params=data, method='POST')
    
    
    def put_opsbro_json(uri, data):
        return get_json(uri, params=data, method='PUT')
    
    
    def delete_opsbro_json(uri):
        return get_json(uri, method='DELETE')


def get_opsbro_agent_state():
    try:
        agent_state = get_opsbro_json('/agent/state')
    except get_request_errors():
        agent_state = 'stopped'
    return agent_state


class NoContextClass(object):
    def __enter__(self):
        pass
    
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class AnyAgent(object):
    def __init__(self):
        self.did_start_a_tmp_agent = False
        self.tmp_agent = None
    
    
    def __enter__(self):
        self.assert_one_agent()
    
    
    def _do_agent_stop(self):
        try:
            get_opsbro_local('/stop')
        except get_request_errors() as exp:
            logger.error(exp)
            return
        agent_state = wait_for_agent_stopped()
        if agent_state != AGENT_STATE_STOPPED:
            logger.error('The temporary agent did not stopped in a valid time. Currently: %s' % agent_state)
            return

    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tmp_agent is not None:
            cprint('')
            cprint('%s Stopping the temporary agent:' % CHARACTERS.corner_top_left, color='grey', end='')
            sys.stdout.flush()
            self._do_agent_stop()
            # Be sure to kill it
            self.tmp_agent.terminate()
            cprint('%s OK' % CHARACTERS.check, color='grey')
            cprint('%s | if you want to start the agent: launch it with the "opsbro agent start" command' % CHARACTERS.corner_bottom_left, color='grey')
    
    
    @staticmethod
    def __tmp_agent_entering():
        os.setsid()
        try:
            from setproctitle import setproctitle
            setproctitle("Temporary agent")
        except ImportError:
            pass
    
    
    # For some CLI we don't care if we have a running agent or just a dummy send (like
    # quick dashboards)
    def assert_one_agent(self):
        agent_state = wait_for_agent_started(visual_wait=True)
        if agent_state == AGENT_STATE_STOPPED:
            self.did_start_a_tmp_agent = True
            tmp_agent_cmd = 'python %s agent start' % get_current_binary()
            logger.debug('Temporary agent command: %s' % tmp_agent_cmd)
            additional_args = {}
            if os.name != 'nt':
                additional_args['preexec_fn'] = self.__tmp_agent_entering
                additional_args['close_fds'] = True
            self.tmp_agent = subprocess.Popen(tmp_agent_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **additional_args)
            cprint('')
            cprint('%s This command need a started agent, and currently no one is started' % CHARACTERS.corner_top_left, color='grey')
            cprint('%s | Spawning a ' % CHARACTERS.vbar, color='grey', end='')
            cprint('temporary one', color='yellow')
            cprint('%s | - process pid is %s' % (CHARACTERS.vbar, self.tmp_agent.pid), color='grey')
            cprint('%s | - you can avoid the temporary agent by launching one with "opsbro agent start" or "/etc/init.d/opsbro start" ' % CHARACTERS.corner_bottom_left, color='grey')
            cprint('')
            agent_state = wait_for_agent_started(visual_wait=True, wait_for_spawn=True)  # note: we wait for spawn as it can take some few seconds before the unix socket is available
        if agent_state == AGENT_STATE_STOPPED:
            raise Exception('Cannot have the agent, even a temporary one')


def wait_for_agent_stopped(timeout=5, visual_wait=False):
    spinners = itertools.cycle(CHARACTERS.spinners)
    start = NOW.monotonic()  # note: thanks to monotonic, we don't care about the system get back in time during this loop
    agent_state = 'unknown'
    while NOW.monotonic() - start < timeout:
        try:
            agent_state = get_opsbro_json('/agent/state')
        except get_request_errors():
            return 'stopped'
        if visual_wait:
            cprint('\r %s ' % next(spinners), color='blue', end='')  # note: spinners.next() do not exists in python3
            cprint(' agent is still ', end='')
            cprint('stopping', color='yellow', end='')
            sys.stdout.flush()
        time.sleep(0.1)
    if visual_wait:
        # Clean what we did put before
        cprint('\r', end='')
        cprint(' ' * 100, end='')
        cprint('\r', end='')
        sys.stdout.flush()
    return agent_state


# Maybe the agent is initializing or not even started (as unix socket).
# Timeout: wait as much time
# visual_wait: during the wait, we can show a spinner and a text to enjoy the user
# exit_if_stopped: if true, sys.exit() directly
# wait_for_spawn: maybe we just did spawn the agent process, but it can take some few seconds before the
# unix socket is available, so allow some stopped state and only exit at the end of the timeout
def wait_for_agent_started(timeout=30, visual_wait=False, exit_if_stopped=False, wait_for_spawn=False):
    spinners = itertools.cycle(CHARACTERS.spinners)
    start = NOW.monotonic()  # note: thanks to monotonic, we don't care about the system get back in time during this loop
    agent_state = 'unknown'
    while NOW.monotonic() - start < timeout:
        try:
            agent_state = get_opsbro_json('/agent/state')
        except get_request_errors():
            agent_state = 'stopped'
        if agent_state == 'stopped':
            # Maybe we need to exit of the daemon is stopped
            if exit_if_stopped:
                cprint('\r', end='')
                logger.error('The agent is stopped')
                sys.exit(2)
            if not wait_for_spawn:
                break
        if agent_state == 'ok':
            break
        if visual_wait:
            cprint('\r %s ' % next(spinners), color='blue', end='')  # note: spinners.next() do not exists in python3
            cprint(' agent is still ', end='')
            cprint('initializing', color='yellow', end='')
            cprint(' (collector, detector,... are not finish)', end='')
            sys.stdout.flush()
        time.sleep(0.1)
    if visual_wait:
        # Clean what we did put before
        cprint('\r', end='')
        cprint(' ' * 100, end='')
        cprint('\r', end='')
        sys.stdout.flush()
    return agent_state


def print_info_title(title):
    print_h1(title)


def print_2tab(e, capitalize=True, col_size=DEFAULT_INFO_COL_SIZE):
    for (k, v) in e:
        label = k
        if capitalize:
            label = label.capitalize()
        s = ' - %s: ' % label
        s = s.ljust(col_size)
        cprint(s, end='', color='blue')
        # If it's a dict, we got additionnal data like color or type
        if isinstance(v, dict):
            color = v.get('color', 'green')
            value = v.get('value')
            cprint(value, color=color)
        else:
            cprint(v, color='green')


class Dummy():
    def __init__(self):
        pass


class CLIEntry(object):
    def __init__(self, f, args, description, allow_temporary_agent, topic):
        self.f = f
        self.args = args
        self.description = description
        self.allow_temporary_agent = allow_temporary_agent
        self.topic = topic


# Commander is the main class for managing the CLI session and behavior
class CLICommander(object):
    def __init__(self, config, opts):
        self.keywords = {}
        self.keywords_topics = {}
        
        self.config = config
        
        log_dir = config.get('log', DEFAULT_LOG_DIR)  # '/var/lib/opsbro'
        log_level = config.get('log_level', 'INFO')
        # early set the logger part
        logger.load(log_dir, '(cli)')
        logger.setLevel(log_level)
        
        cfg_dir = DEFAULT_CFG_DIR
        if not os.path.exists(cfg_dir):
            logger.error('Configuration directory [%s] is missing' % cfg_dir)
            sys.exit(2)
        
        # We need the main cfg_directory
        configmgr.load_cfg_dir(cfg_dir, load_focus='agent')
        
        data_dir = os.path.abspath(os.path.join(DEFAULT_DATA_DIR))  # '/var/lib/opsbro/'
        
        # We can start with a void data dir
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        
        # Then we will need to look at other directories, list from
        # * core-configuration = fill by installation, read-only
        # * global-configration = common to all nodes
        # * zone-configuration = common to zone nodes
        # * local-configuration = on this specific node
        core_configuration = os.path.join(data_dir, 'core-configuration')
        global_configuration = os.path.join(data_dir, 'global-configuration')
        zone_configuration = os.path.join(data_dir, 'zone-configuration')
        local_configuration = os.path.join(data_dir, 'local-configuration')
        
        # Ask the packer to load pack descriptions so it will be able to
        # give us which pack directories must be read (with good order)
        packer.load_pack_descriptions(core_configuration, 'core')
        packer.load_pack_descriptions(global_configuration, 'global')
        packer.load_pack_descriptions(zone_configuration, 'zone')
        packer.load_pack_descriptions(local_configuration, 'local')
        
        # Now that packs are load and clean, we can load collector code from it
        configmgr.load_collectors_from_packs()
        
        # also load hosting driver (like EC2 or scaleway) from packs too
        configmgr.load_hostingdrivers_from_packs()
        
        # load all compliance drivers
        configmgr.load_compliancebackends_from_packs()
        
        # Now that packs are load and clean, we can load modules code from it
        configmgr.load_modules_from_packs()
        
        # We load configuration from packs, but only the one we are sure we must load
        configmgr.load_configuration_from_packs()
        
        # We can now give configuration to the collectors
        collectormgr.get_parameters_from_packs()
        
        # We can now give configuration to the modules
        modulemanager.get_parameters_from_packs()
        
        # We will now try to load the keywords from the modules
        self.load_cli_mods(opts)
    
    
    # We should look on the sys.argv if we find a valid keywords to
    # call in one loop or not.
    def hack_sys_argv(self):
        command_values = []  # Know which function to CALL
        internal_values = []  # with which parameters
        
        founded = False
        ptr = self.keywords
        
        for arg in sys.argv[1:]:  # don't care about the program name
            # Maybe it's a global one
            if not founded and arg in self.keywords['global']:
                founded = True
                command_values.insert(0, 'global')
            if not founded and arg in ptr:
                founded = True
            # Did we found it?
            if founded:
                command_values.append(arg)
            else:  # ok still not, it's for the opsbro command so
                internal_values.append(arg)
        
        logger.debug('Internal args %s' % internal_values)
        logger.debug('Command values %s' % command_values)
        
        # Ok, really hack sys.argv to catch PURE cli argument (like -D or -h)
        sys.argv = internal_values
        return command_values
    
    
    # For some keywords, find (and create if need) the keywords entry in the keywords tree
    def insert_keywords_entry(self, keywords, e):
        
        # Simulate 'global' entry before top level entries
        if len(keywords) == 1:
            keywords = ['global', keywords[0]]
        
        # Take the first keyword and save the topics from it
        keyword = keywords[0]
        if keyword not in self.keywords_topics:
            self.keywords_topics[keyword] = set()
        self.keywords_topics[keyword].add(e.topic)
        
        # Go for save as tree
        ptr = self.keywords
        for keyword in keywords[:-1]:
            if keyword not in ptr:
                ptr[keyword] = {}
            ptr = ptr[keyword]
        entry_last_key = keywords[-1]
        ptr[entry_last_key] = e
    
    
    def _create_cli_entry(self, f, raw_entry, topics):
        # We need to have only one topic for this entry, so take the most significative one
        if not topics:
            main_topic = 'generic'
        else:
            main_topic = topics[0]
        m_keywords = raw_entry.get('keywords', [])
        args = raw_entry.get('args', [])
        description = raw_entry.get('description', '')
        allow_temporary_agent = raw_entry.get('allow_temporary_agent', None)
        e = CLIEntry(f, args, description, allow_temporary_agent, main_topic)
        # Finally save it
        self.insert_keywords_entry(m_keywords, e)
    
    
    def get_cli_entry_from_args(self, command_args):
        logger.debug("ARGS: %s" % command_args)
        if len(command_args) == 1:
            command_args = ['global', command_args[0]]
        
        ptr = self.keywords
        for arg in command_args:
            if arg not in ptr:
                logger.error('UNKNOWN command argument %s' % arg)
                return None
            ptr = ptr[arg]
            # Reached a leaf
            if isinstance(ptr, CLIEntry):
                return ptr
        return ptr
    
    
    def load_cli_mods(self, opts):
        global CONFIG
        # Main list of keywords for the first parameter
        self.keywords.clear()
        self.keywords_topics.clear()
        
        # CLI are load from the packs
        cli_mods_dirs = []
        pack_directories = packer.give_pack_directories_to_load()
        
        for (pname, level, dir) in pack_directories:
            cli_directory = os.path.join(dir, 'cli')
            if os.path.exists(cli_directory):
                cli_mods_dirs.append((pname, cli_directory))
        
        logger.debug("Loading the cli directories %s" % cli_mods_dirs)
        
        # Link the CONFIG objet into the common
        # cli mod
        CONFIG = self.config
        
        for (pname, dir) in cli_mods_dirs:
            f = os.path.join(dir, 'cli.py')
            if os.path.exists(f):
                dname = os.path.split(dir)[1]
                # Let's load it, but first att it to sys.path
                sys.path.insert(0, dir)
                # Load this PATH/cli.py file
                m = imp.load_source(dname, f)
                # Unset this sys.path hook, we do not need anymore
                sys.path = sys.path[1:]
                
                exports = getattr(m, 'exports', {})
                # get the topics from the pack definition
                topics = packer.get_pack_all_topics(pname)
                for (f, raw_entry) in exports.items():
                    self._create_cli_entry(f, raw_entry, topics)
        
        logger.debug('We load the keywords %s' % self.keywords)
    
    
    # We need to have the command arguments clean from the keywords, so we only have the argument of the function()
    # that will be called
    def clean_command_args(self, command_args):
        ptr = self.keywords
        idx = 0
        for arg in command_args:
            if arg not in ptr:
                return command_args[idx:]
            ptr = ptr[arg]
            idx += 1
            if isinstance(ptr, CLIEntry):
                return command_args[idx:]
        return []
    
    
    # Look at entry like allow_temporary_agent and give a matching context
    @staticmethod
    def __get_execution_context(entry):
        temp_agent = entry.allow_temporary_agent
        if temp_agent is None:
            return NoContextClass()
        if temp_agent.get('enabled', False):
            return AnyAgent()
        return NoContextClass()
    
    
    # Execute a function based on the command line
    def one_loop(self, command_args):
        logger.debug("ARGS: %s" % command_args)
        
        entry = self.get_cli_entry_from_args(command_args)
        if entry is None:
            self.print_list(command_args[0])
            sys.exit(2)
        
        command_args = self.clean_command_args(command_args)
        
        # Now prepare a new parser, for the command call this time
        command_parser = optparse.OptionParser('', version="%prog " + VERSION)
        command_parser.prog = ''
        
        for a in entry.args:
            n = a.get('name', None)
            if n is None:
                continue
            default = a.get('default', Dummy())
            description = a.get('description', '')
            _type = a.get('type', 'standard')
            if n.startswith('-'):
                # Get a clean version of the parameter, without - or --
                dest = n[1:]
                if dest.startswith('-'):
                    dest = dest[1:]
                # And if the parameter is like download-only, map it to
                # download_only
                dest = dest.replace('-', '_')
                # add_option parameters, common ones
                d = {'dest': dest, 'help': (description)}
                # Specify the types allowed for parameters
                if _type == 'bool':
                    d['action'] = 'store_true'
                elif _type == 'int' or _type == 'long':
                    d['type'] = 'int'
                elif _type == 'float':
                    d['type'] = 'float'
                
                # and if we got a real default, use it
                if not isinstance(default, Dummy):
                    d['default'] = default
                command_parser.add_option(n, **d)
        
        cmd_opts, cmd_args = command_parser.parse_args(command_args)
        f = entry.f
        logger.debug("CALLING " + str(f) + " WITH " + str(cmd_args) + " and " + str(cmd_opts))
        
        # Look if this call need a specific execution context, like a temporary agent
        execution_ctx = self.__get_execution_context(entry)
        with execution_ctx:
            try:
                f(*cmd_args, **cmd_opts.__dict__)
            except TypeError as exp:
                logger.error('Bad call: missing or too much arguments: %s (%s)' % (exp, str(traceback.print_exc())))
                sys.exit(2)
            except Exception:
                logger.error('The call did fail: %s' % (str(traceback.print_exc())))
                sys.exit(2)
    
    
    def print_completion(self, args):
        to_analayses = []
        for (k, d) in self.keywords.items():
            if k != 'global':
                to_analayses.append([k])
                for sub_k in d.keys():
                    to_analayses.append([k, sub_k])
            else:
                for sub_k in d.keys():
                    to_analayses.append([sub_k])
        
        for to_analyse in to_analayses:
            # if we are too far in the command, cannot be this one
            if len(args) > len(to_analyse):
                continue
        
        res = []
        # so args <= to_analyse
        # Special case: no args, give only first level items
        if len(args) == 0:
            for to_analyse in to_analayses:
                if len(to_analyse) == 1:
                    res.append(to_analyse[0])
        elif len(args) == 1:
            arg = args[0]
            # Maybe it's a keyword, if so automatically give sub commands
            if arg in self.keywords:
                d = self.keywords[arg]
                res = d.keys()
            elif arg in self.keywords['global']:  # maybe in global directly
                res = self.keywords['global'].keys()
            else:  # ok not directly a keyword, try to match
                for k in self.keywords.keys():
                    if k.startswith(arg):
                        res.append(k)
                # Also look at global entries
                for k in self.keywords['global'].keys():
                    if k.startswith(arg):
                        res.append(k)
        else:  # ok we will have to match/filter something
            # Maybe we have a perfect entry, if so return nothing because we already found the entry
            perfect_match = False
            for to_analyse in to_analayses:
                if to_analyse == args:
                    perfect_match = True
            # Ok try to guess so
            if not perfect_match:
                last_partial = args[-1]
                full_match = args[:-1]
                for to_analyse in to_analayses:
                    propose_last_partial = to_analyse[-1]
                    propose_full_match = to_analyse[:-1]
                    if propose_full_match != full_match:  # This propose entry is not matching full match
                        continue
                    if propose_last_partial.startswith(last_partial):  # valid entry found
                        res.append(propose_last_partial)
        
        cprint(' '.join(res))
        return
    
    
    @staticmethod
    def __chunker(seq, size):
        return [seq[pos:pos + size] for pos in xrange(0, len(seq), size)]
    
    
    # Ok magic ahead: we will try to look at printing the options with color
    # AND by looking at the terminal width to have a responsive display
    def __print_sub_level_tree(self, ptr, prefix, first_level=False):
        cmds = list(ptr.keys())  # note: python3 keys is not a list
        cmds.sort()
        
        _, term_width = self.__get_terminal_size()
        
        # We want to colorize only the first element, then
        # grey common parts
        full_colorize = True
        for k in cmds:
            entry = ptr[k]
            # Tree not finish? go for it
            if isinstance(entry, dict):
                self.__print_sub_level_tree(entry, '%s %s' % (prefix, k))
                continue
            nb_chars = 0
            s = k.ljust(25)
            if prefix:
                if full_colorize:
                    # We need to get the size of the colorless verion, to have the number of spaces need
                    colorless_s = '%s %s' % (prefix, k)
                    len_colorless_raw = len(colorless_s)
                    colorless_s = colorless_s.ljust(25)
                    nb_chars += len(colorless_s)
                    # now really colorize it
                    s = '%s %s' % (prefix, sprintf(k, color='green'))
                    if len_colorless_raw < 25:
                        s = s + ' ' * (25 - len_colorless_raw)
                    
                    # Maybe the prefix was long, if so, do not
                    _elts = prefix.split(' ')
                    
                    # The very first element must be green, then we must the prefix as grey
                    first_part_color = 'green' if first_level else 'grey'
                    new_elts = []
                    new_elts.append((_elts[0], sprintf(_elts[0], color=first_part_color)))
                    for p in _elts[1:]:
                        new_elts.append((p, sprintf(p, color='green')))
                    for (p, changed_p) in new_elts:
                        s = s.replace(p, changed_p, 1)
                    full_colorize = False
                else:
                    s = '%s %s' % (prefix, k)
                    s = s.ljust(25)
                    nb_chars += len(s)
                    s = s.replace(prefix, sprintf(prefix, color='grey'), 1)
                    s = s.replace(k, sprintf(k, color='green'), 1)
            else:
                # Simple level parameters, so banner, version, etc
                nb_chars += len(s)  # note: before colorize it
                s = sprintf(s, color='green')
            topic_color_ix = topiker.get_color_id_by_topic_string(entry.topic)
            topic_prefix = '%s' % (lolcat.get_line(CHARACTERS.vbar, topic_color_ix, spread=None))
            cprint(topic_prefix, end='')
            cprint('  opsbro ', color='grey', end='')
            nb_chars += 13
            cprint('%s ' % s, end='')
            available_width = max(10, term_width - nb_chars)
            cprint(': ', end='')
            
            # Responsive description display
            description = entry.description
            chunks = self.__chunker(description, available_width)
            cprint(chunks[0])
            if len(chunks) > 1:
                for chunk in chunks[1:]:
                    cprint(topic_prefix, end='')
                    cprint(' ' * (nb_chars - 1), end='')
                    cprint(chunk)
    
    
    @staticmethod
    def __get_terminal_size():
        try:
            height, width = get_terminal_size()
        except:
            height = width = 999
        return height, width
    
    
    def print_list(self, keyword=''):
        cprint('')
        print_h1('Available commands')
        sub_cmds = list(self.keywords.keys())  # note: python 3 keys is not a list
        sub_cmds.remove('global')
        sub_cmds.sort()
        sub_cmds.insert(0, 'global')
        
        for cmd in sub_cmds:
            # If we did filter a specific keyword, bailout this
            # one
            if keyword and cmd != keyword:
                continue
            prefix = cmd
            if cmd == 'global':
                prefix = ''
            d = self.keywords[cmd]
            topics_strings = list(self.keywords_topics[cmd])
            topics_strings.sort()
            topic_string = topics_strings[0]
            topic_color = topiker.get_color_id_by_topic_string(topic_string)
            cprint(lolcat.get_line(u'%s%s ' % (CHARACTERS.corner_top_left, CHARACTERS.hbar * 10), topic_color, spread=None), end='')
            cprint(u'%-15s' % cmd, color='magenta', end='')
            numerical = 's' if len(topics_strings) > 1 else ''
            cprint(' (topic%s: %s)' % (numerical, ', '.join([topic_string for topic_string in topics_strings])), color='grey')
            self.__print_sub_level_tree(d, prefix, first_level=True)
            cprint('')
        return
