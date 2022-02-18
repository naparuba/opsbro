#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import time
import sys
import os

from opsbro.info import VERSION
from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors, get_not_critical_request_errors
from opsbro.cli import get_opsbro_json
from opsbro.cli_display import print_h1, print_h2, get_terminal_size
from opsbro.compliancemgr import COMPLIANCE_LOG_COLORS, COMPLIANCE_STATES, COMPLIANCE_STATE_COLORS
from opsbro.jsonmgr import jsoner
from opsbro.util import bytes_to_unicode


def __get_ssh_args(user=None, keyfile=None):
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


def __scp_file(ip, src_path, dst_path, user=None, keyfile=None):
    import subprocess  # lazy load
    
    ssh_args = __get_ssh_args(user, keyfile)
    cmd = u'/usr/bin/scp %s "%s" %s:%s' % (ssh_args, src_path, ip, dst_path)
    
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid, env={'LANG': 'C'})
    stdout, stderr = p.communicate()
    logger.debug('[SCP:] STDOUT: %s' % stdout)
    logger.debug('[SCP:] STDERR: %s' % stderr)
    if p.returncode != 0:
        cprint('ERROR: cannot copy %s to %s: %s' % (src_path, ip, stdout + stderr), color='red')
        sys.exit(2)


def __ssh_command(ip, dst_command, user=None, keyfile=None):
    import subprocess  # lazy load
    
    ssh_args = __get_ssh_args(user, keyfile)
    cmd = u'/usr/bin/ssh %s %s "%s"' % (ssh_args, ip, dst_command)
    
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid, env={'LANG': 'C'})
    stdout, stderr = p.communicate()
    stdout = bytes_to_unicode(stdout)
    stderr = bytes_to_unicode(stderr)
    logger.debug('[SSH: %s] STDOUT: %s' % (cmd, stdout))
    logger.debug('[SSH: %s] STDERR: %s' % (cmd, stderr))
    if p.returncode != 0:
        cprint('ERROR: cannot execute the command "%s" to %s: %s' % (dst_command, ip, stdout + stderr), color='red')
        sys.exit(2)


def do_new(ip, timeout=30, join_us=True):
    # If we are asking to join us, we will have our public ip
    our_ip = u''
    if join_us:
        try:
            d = get_opsbro_json('/agent/info')
        except get_request_errors() as exp:
            logger.error('Cannot join opsbro agent for get our IP: %s' % exp)
            sys.exit(1)
        our_ip = d.get('public_addr', None)
        if our_ip is None:
            cprint('Cannot get our public IP, exiting')
            sys.exit(1)
    
    cprint(u'Launching new installation on %s:' % ip)
    
    cprint(u'  - copying the installation source:', end='')
    __scp_file(ip, u'/var/lib/opsbro/installation-source.tar.gz', '/root')
    cprint(CHARACTERS.check, color='green')
    
    cprint(u'  - executing the installation:', end='')
    __ssh_command(ip, u'cd /root;tar xfz installation-source.tar.gz;ls -thor;cd opsbro-%s;(python3 setup.py install ||python2 setup.py install);/etc/init.d/opsbro start' % VERSION)
    cprint(CHARACTERS.check, color=u'green')
    
    if join_us:
        cprint(u'  - Asking the other node to join us at %s:' % our_ip, end='')
        __ssh_command(ip, u'opsbro gossip join "%s"' % our_ip)
        cprint(CHARACTERS.check, color='green')


exports = {
    do_new: {
        'keywords'             : ['deploy', 'new'],
        'description'          : 'Deploy the agent to another server',
        'args'                 : [
            {'name': 'ip', 'description': 'IP of the new server'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
            {'name': '--join-us', 'type': 'bool', 'default': True, 'description': 'If enabled (default), it will join the other node with our public address'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        
    },
    
}
