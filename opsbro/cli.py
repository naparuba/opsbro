# -*- coding: utf-8 -*-

import os
import json
import requests
import imp
import traceback
import sys
import optparse

from opsbro.configurationmanager import configmgr
from opsbro.collectormanager import collectormgr
from opsbro.modulemanager import modulemanager
from opsbro.packer import packer
from opsbro.unixclient import get_json, get_local
from opsbro.log import cprint, logger
from opsbro.defaultpaths import DEFAULT_LOG_DIR, DEFAULT_CFG_DIR, DEFAULT_DATA_DIR
from opsbro.info import VERSION
from opsbro.cli_display import print_h1
from opsbro.characters import CHARACTERS
from opsbro.misc.lolcat import lolcat

# Will be populated by the opsbro CLI command
CONFIG = None


def get_local_socket():
    return CONFIG.get('socket', '/var/lib/opsbro/opsbro.sock')


if os.name != 'nt':
    def get_opsbro_json(uri):
        local_socket = get_local_socket()
        return get_json(uri, local_socket)
    
    
    def get_opsbro_local(uri):
        local_socket = get_local_socket()
        return get_local(uri, local_socket)
    
    
    def post_opsbro_json(uri, data):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, params=data, method='POST')
    
    
    def put_opsbro_json(uri, data):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, params=data, method='PUT')
else:
    def get_opsbro_json(uri):
        r = requests.get('http://127.0.0.1:6770%s' % uri)
        obj = json.loads(r.text)
        return obj
    
    
    def get_opsbro_local(uri):
        r = requests.get('http://127.0.0.1:6770%s' % uri)
        status = r.status_code
        text = r.text
        return (status, text)
    
    
    def post_opsbro_json(uri, data):
        return get_json(uri, params=data, method='POST')
    
    
    def put_opsbro_json(uri, data):
        return get_json(uri, params=data, method='PUT')


def print_info_title(title):
    print_h1(title)


def print_2tab(e, capitalize=True, col_size=20):
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
            _type = v.get('type', 'std')
            value = v.get('value')
            cprint(value, color=color)
        else:
            cprint(v, color='green')


class Dummy():
    def __init__(self):
        pass


class CLIEntry(object):
    def __init__(self, f, args, description):
        self.f = f
        self.args = args
        self.description = description


# Commander is the main class for managing the CLI session and behavior
class CLICommander(object):
    def __init__(self, config, opts):
        self.keywords = {}
        
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
        # * global-configration = common to all nodes
        # * zone-configuration = common to zone nodes
        # * local-configuration = on this specific node
        global_configuration = os.path.join(data_dir, 'global-configuration')
        zone_configuration = os.path.join(data_dir, 'zone-configuration')
        local_configuration = os.path.join(data_dir, 'local-configuration')
        
        # Ask the packer to load pack descriptions so it will be able to
        # give us which pack directories must be read (with good order)
        packer.load_pack_descriptions(global_configuration, 'global')
        packer.load_pack_descriptions(zone_configuration, 'zone')
        packer.load_pack_descriptions(local_configuration, 'local')
        
        # Now that packs are load and clean, we can load collector code from it
        configmgr.load_collectors_from_packs()
        
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
        ptr = self.keywords
        for keyword in keywords[:-1]:
            if keyword not in ptr:
                ptr[keyword] = {}
            ptr = ptr[keyword]
        entry_last_key = keywords[-1]
        ptr[entry_last_key] = e
    
    
    def create_cli_entry(self, f, raw_entry):
        m_keywords = raw_entry.get('keywords', [])
        args = raw_entry.get('args', [])
        description = raw_entry.get('description', '')
        e = CLIEntry(f, args, description)
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
        
        # CLI are load from the packs
        cli_mods_dirs = []
        pack_directories = packer.give_pack_directories_to_load()
        
        for (pname, level, dir) in pack_directories:
            cli_directory = os.path.join(dir, 'cli')
            if os.path.exists(cli_directory):
                cli_mods_dirs.append(cli_directory)
        
        logger.debug("Loading the cli directories %s" % cli_mods_dirs)
        
        # Link the CONFIG objet into the common
        # cli mod
        CONFIG = self.config
        
        for d in cli_mods_dirs:
            f = os.path.join(d, 'cli.py')
            if os.path.exists(f):
                dname = os.path.split(d)[1]
                # Let's load it, but first att it to sys.path
                sys.path.insert(0, d)
                # Load this PATH/cli.py file
                m = imp.load_source(dname, f)
                # Unset this sys.path hook, we do not need anymore
                sys.path = sys.path[1:]
                
                exports = getattr(m, 'exports', {})
                for (f, raw_entry) in exports.iteritems():
                    self.create_cli_entry(f, raw_entry)
        
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
    
    
    # Execute a function based on the command line
    def one_loop(self, command_args):
        logger.debug("ARGS: %s" % command_args)
        
        entry = self.get_cli_entry_from_args(command_args)
        if entry is None:
            self.print_list(command_args[0])
            return
        
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
                # If bool setup it
                if _type == 'bool':
                    d['action'] = 'store_true'
                # and if we got a real default, use it
                if not isinstance(default, Dummy):
                    d['default'] = default
                command_parser.add_option(n, **d)
        
        cmd_opts, cmd_args = command_parser.parse_args(command_args)
        f = entry.f
        logger.debug("CALLING " + str(f) + " WITH " + str(cmd_args) + " and " + str(cmd_opts))
        try:
            f(*cmd_args, **cmd_opts.__dict__)
        except TypeError, exp:
            logger.error('Bad call: missing or too much arguments: %s' % exp)
            sys.exit(2)
        except Exception, exp:
            logger.error('The call did fail: %s' % (str(traceback.print_exc())))
    
    
    def print_completion(self, args):
        to_analayses = []
        for (k, d) in self.keywords.iteritems():
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
                # print "SKIP impossible match", to_analyse
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
                    # print "PERFECT FIT", to_analyse
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
        
        print ' '.join(res)
        return
    
    
    def __print_sub_level_tree(self, ptr, prefix):
        cmds = ptr.keys()
        cmds.sort()
        for k in cmds:
            entry = ptr[k]
            # Tree not finish? go for it
            if isinstance(entry, dict):
                self.__print_sub_level_tree(entry, '%s %s' % (prefix, k))
                continue
            s = k.ljust(25)
            if prefix:
                s = '%s %s' % (prefix, k)
                s = s.ljust(25)
            #topic_prefix = '%s' % (lolcat.get_line(CHARACTERS.topic_display_prefix, 26, spread=None))
            #cprint(topic_prefix, end='')
            cprint('  opsbro ', color='grey', end='')
            cprint('%s ' % s, 'green', end='')
            cprint(': %s' % entry.description)
    
    
    def print_list(self, keyword=''):
        print "Available commands:"
        sub_cmds = self.keywords.keys()
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
            print_h1(cmd, only_first_part=True, line_color='blue', title_color='magenta')
            self.__print_sub_level_tree(d, prefix)
        return
