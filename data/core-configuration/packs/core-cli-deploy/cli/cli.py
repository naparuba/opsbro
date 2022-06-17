#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function

import os
import itertools
import sys
import time

from opsbro.characters import CHARACTERS
from opsbro.cli import get_opsbro_json
from opsbro.info import VERSION
from opsbro.log import cprint, logger, sprintf
from opsbro.threadmgr import threader
from opsbro.unixclient import get_request_errors
from opsbro.util import bytes_to_unicode
from opsbro.type_hint import TYPE_CHECKING

if TYPE_CHECKING:
    from opsbro.type_hint import Tuple, Optional


class UpdateExecution(object):
    def __init__(self, member=None, ip=None):
        self._status = u'PENDING'
        self._rc = 0
        self._error = u''
        self._member = member
        if self._member:
            self._name = member['name']
            self._display_name = member['display_name']
            self._zone = member['zone']
            self._ip = member['public_addr']
            if self._display_name:
                self._display_str = '%s [%s] [zone=%s][ip=%s]' % (self._name, sprintf(self._display_name, color='magenta', end=''), self._zone, self._ip)
            else:
                self._display_str = '%s [zone=%s] [ip=%s]' % (sprintf(self._name, color='magenta', end=''), self._zone, self._ip)
        else:
            self._ip = ip
            self._display_str = '%s [name=unknown]' % (sprintf(self._ip, color='magenta', end=''))
    
    
    def start(self):
        self._status = u'STARTED'
    
    
    def is_finish(self):
        return self._status == u'FINISH'
    
    
    def set_finish_ok(self):
        self._status = u'FINISH'
    
    
    def set_finish_error(self, err):
        self._status = u'FINISH'
        self._rc = 2
        self._error = err
    
    
    def print_finish(self):
        
        if self._rc == 0:
            cprint(' %s ' % CHARACTERS.check, color='green', end='')
            cprint(self._display_str, end='')
            return
        # bad state ^^
        cprint(' %s ' % CHARACTERS.cross, color='red', end='')
        cprint('%s :' % self._display_str)
        cprint(self._error, color='grey')
        
        sys.stdout.flush()
        return


def __get_ssh_args(user=None, keyfile=None):
    # type: (Optional[str], Optional[str]) -> str
    # note: lang=C + shell so we can be sure we will have errors in english to grep them!
    # note2: -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ==> do not look at host authorization
    # note3: -o BatchMode=yes => do not prompt password or such things
    # note4: -o ExitOnForwardFailure=true => if forward fail, exit!
    # note5: "root" user is strictly forbidden to prevent huge security holes
    # note6: -4 : ipv4 only, so it won't open only ipv6 if ipv4 is unbindable
    # note7: -o PreferredAuthentications=publickey : we do connect with key, so directly skip other methods
    
    ssh_args = ' -4 -o PreferredAuthentications=publickey -o ExitOnForwardFailure=true -o BatchMode=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no '
    
    if user is not None and user != "" and user != 'root':
        ssh_args += ' -l "%s"' % user
    
    if keyfile is not None and keyfile != "":
        ssh_args += ' -i "%s"' % os.path.expanduser(keyfile)
    
    return ssh_args


def _launch_process(cmd):
    import subprocess  # lazy load
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid, env={'LANG': 'C'})
    stdout, stderr = p.communicate()
    stdout = bytes_to_unicode(stdout)
    stderr = bytes_to_unicode(stderr)
    rc = p.returncode
    return rc, stdout, stderr


def __scp_file(ip, src_path, dst_path, user=None, keyfile=None):
    # type: (str, str, str, Optional[str], Optional[str]) -> Tuple[bool, str]
    
    ssh_args = __get_ssh_args(user, keyfile)
    cmd = u'/usr/bin/scp %s "%s" %s:%s' % (ssh_args, src_path, ip, dst_path)
    
    rc, stdout, stderr = _launch_process(cmd)
    logger.debug('[SCP:] STDOUT: %s' % stdout)
    logger.debug('[SCP:] STDERR: %s' % stderr)
    if rc != 0:
        ret = sprintf('ERROR: cannot copy %s to %s: %s' % (src_path, ip, stdout + stderr), color='red')
        return False, ret
    return True, u''


def __ssh_command(ip, dst_command, user=None, keyfile=None):
    # type: (str, str, Optional[str], Optional[str]) -> Tuple[bool, str]
    
    ssh_args = __get_ssh_args(user, keyfile)
    cmd = u'/usr/bin/ssh %s %s "%s"' % (ssh_args, ip, dst_command)
    
    rc, stdout, stderr = _launch_process(cmd)
    logger.debug('[SSH: %s] STDOUT: %s' % (cmd, stdout))
    logger.debug('[SSH: %s] STDERR: %s' % (cmd, stderr))
    if rc != 0:
        err = sprintf('ERROR: cannot execute the command "%s" to %s: %s' % (dst_command, ip, stdout + stderr), color='red')
        return False, err
    return True, u''


def _get_our_ip():
    try:
        d = get_opsbro_json('/agent/info')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent for get our IP: %s' % exp)
        sys.exit(1)
    our_ip = d.get('public_addr', None)
    if our_ip is None:
        cprint('Cannot get our public IP, exiting')
        sys.exit(1)
    return our_ip


def do_new(ip, timeout=30, join_us=True):
    # If we are asking to join us, we will have our public ip
    our_ip = u''
    if join_us:
        our_ip = _get_our_ip()
    
    cprint(u'Launching new installation on %s:' % ip)
    
    cprint(u'  - copying the installation source:', end='')
    r, err = __scp_file(ip, u'/var/lib/opsbro/installation-source.tar.gz', '/root')
    if r:
        cprint(CHARACTERS.check, color='green')
    else:
        cprint(err, end=u'')
        sys.exit(2)
    
    cprint(u'  - executing the installation:', end='')
    r, err = __ssh_command(ip, u'cd /root;rm -fr opsbro-%s;tar xfz installation-source.tar.gz;ls -thor;cd opsbro-%s;(python3 setup.py install ||python2 setup.py install);/etc/init.d/opsbro start' % (VERSION, VERSION))
    if r:
        cprint(CHARACTERS.check, color=u'green')
    else:
        cprint(err, end=u'')
        sys.exit(2)
    
    if join_us:
        cprint(u'  - Asking the other node to join us at %s:' % our_ip, end='')
        r, err = __ssh_command(ip, u'opsbro gossip join "%s"' % our_ip)
        if r:
            cprint(CHARACTERS.check, color='green')
        else:
            cprint(err, end=u'')
            sys.exit(2)
    sys.exit(0)


def _get_list_of_all_updates():
    try:
        all_members = get_opsbro_json('/agent/members').values()
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to list members: %s' % exp)
        sys.exit(1)
    
    every_one = []
    for member in all_members:
        entry = {'name'        : member['name'],
                 'display_name': member['display_name'],
                 'zone'        : member['zone'],
                 'public_addr' : member['public_addr'],
                 }
        every_one.append(entry)
    return every_one


def do_update(ip, everyone=False, timeout=30, join_us=False):
    # If we are asking to join us, we will have our public ip
    
    our_ip = u''
    if join_us:
        our_ip = _get_our_ip()
    
    if ip:
        execution = UpdateExecution(ip=ip)
        _do_update_on_ip(ip, our_ip, join_us, execution)
        _wait_for_executions({ip: execution})
        sys.exit(0)
    
    if everyone:
        
        all_members = _get_list_of_all_updates()
        executions = {}
        for member in all_members:
            ip = member['public_addr']
            executions[ip] = UpdateExecution(member=member)
        
        for member in all_members:
            name = member['name']
            ip = member['public_addr']
            cprint(u' - Updating %s (%s):' % (name, ip))
            sys.stdout.flush()
            threader.create_and_launch(_do_update_on_ip, (ip, our_ip, join_us, executions[ip]), 'update-%s' % ip, essential=True)
        
        _wait_for_executions(executions)


def _wait_for_executions(executions):
    spinners = itertools.cycle(CHARACTERS.spinners)
    finished = set()
    still_running = True
    while still_running:
        did_print = False
        nb_running = 0
        still_running = False
        for ip, execution in executions.items():  # type: (str, UpdateExecution)
            if ip in finished:  # already shown
                continue
            if not execution.is_finish():
                still_running = True
                nb_running += 1
            else:  # just finish
                finished.add(ip)
                cprint(u'')
                execution.print_finish()
                did_print = True
        if nb_running == 0:
            cprint(u'')
            return
        if did_print:  # we must return the line as the print_finish did not return \n
            cprint(u'')
        _nb_spins = 5
        for i in range(_nb_spins):
            cprint('\r%s %d updates still running' % (next(spinners), nb_running), end='')
            time.sleep(1.0 / _nb_spins)


def _do_update_on_ip(ip, our_ip, join_us, execution_entry):
    # type: (str, str, bool, Optional[UpdateExecution]) -> None
    
    execution_entry.start()
    
    r, err = __scp_file(ip, u'/var/lib/opsbro/installation-source.tar.gz', '/root')
    if not r:
        execution_entry.set_finish_error(u'Fail to copy the installation package: %s' % err)
        return
    
    r, err = __ssh_command(ip,
                           u'/etc/init.d/opsbro stop;cd /root;rm -fr opsbro-%s;tar xfz installation-source.tar.gz;ls -thor;cd opsbro-%s;(python3 setup.py install --update --update-global-packs||python2 setup.py install --update --update-global-packs);/etc/init.d/opsbro start' % (
                               VERSION, VERSION))
    if not r:
        execution_entry.set_finish_error('Fail to update on the distant server: %s' % err)
        return
    
    if join_us:
        r, err = __ssh_command(ip, u'opsbro gossip join "%s"' % our_ip)
        if not r:
            execution_entry.set_finish_error('Fail to join our node: %s' % err)
            return
    
    execution_entry.set_finish_ok()
    return


exports = {
    do_new   : {
        'keywords'             : ['deploy', 'new'],
        'description'          : 'Deploy the agent to another server',
        'args'                 : [
            {'name': '--ip', 'default': '', 'description': 'IP of the new server'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
            {'name': '--join-us', 'type': 'bool', 'default': True, 'description': 'If enabled (default), it will join the other node with our public address'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        
    },
    
    do_update: {
        'keywords'             : ['deploy', 'update'],
        'description'          : 'Update the agent to another server with your version',
        'args'                 : [
            {'name': '--ip', 'default': '', 'description': 'IP of the new server'},
            {'name': '--everyone', 'type': 'bool', 'default': False, 'description': 'If enabled (disabled by default), it try to update all our gossip members'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the update'},
            {'name': '--join-us', 'type': 'bool', 'default': False, 'description': 'If enabled (disabled by default), it will join the other node with our public address'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        
    },
    
}
