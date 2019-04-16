#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
import re
import stat
import optparse
import shutil
import imp
import codecs

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
from glob import glob
import atexit

# We have some warnings because we reimport some libs. We don't want them to be shown at install
import warnings

PY3 = sys.version_info >= (3,)
if PY3:
    basestring = str  # no basestring in python 3


def _disable_warns(*args, **kwargs):
    pass


warnings.showwarning = _disable_warns

# will fail under 2.5 python version, but if really you have such a version in
# prod you are a morron and we can't help you
python_version = sys.version_info
if python_version < (2, 6):
    sys.exit("OpsBro require as a minimum Python 2.6, sorry")
# elif python_version >= (3,):
#    sys.exit("OpsBro is not yet compatible with Python 3.x, sorry")

package_data = ['*.py']

# Is this setup.py call for a pypi interaction? if true, won't hook lot of things
is_pypi_register_upload = ('register' in sys.argv or ('sdist' in sys.argv and 'upload' in sys.argv))
if is_pypi_register_upload:
    print("Pypi specal mode activated, skipping some black magic")
    if '-v' not in sys.argv:
        sys.argv.append('-v')

# Is it a first step installation for pip? (egg_info stuff)
is_pip_first_step = 'egg_info' in sys.argv
# Last step for pip insta an install one (at least in pip 9.0.1)
is_pip_real_install_step = 'bdist_wheel' in sys.argv

# Black magic install:
# * copy /etc
# * look for dependencies from system packages
# * hide setup.py part
# If not black kmagic (like in pip first step, or pypi interaction (upload, etc)
# we do not want any black magic thing, and we try to behave like a standard python package ^^
# By default we love black magic, but if we are in a pip special call or pypi, we disable it
allow_black_magic = not is_pypi_register_upload and not is_pip_first_step

# We will need to allow a debug of the orig_sys_argv
orig_sys_argv = sys.argv[:]


##################################       Utility functions for files
# helper function to read the README file
def read(fname):
    return codecs.open(os.path.join(os.path.dirname(__file__), fname), 'r', 'utf8').read()


# Do a chmod -R +x
def _chmodplusx(d):
    if not os.path.exists(d):
        return
    if os.path.isdir(d):
        for item in os.listdir(d):
            p = os.path.join(d, item)
            if os.path.isdir(p):
                _chmodplusx(p)
            else:
                st = os.stat(p)
                os.chmod(p, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    else:
        st = os.stat(d)
        os.chmod(d, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


##################################       Hook the ugly python setup() call that can output gcc warnings.
# NOTE: yes, there is os.dup and file descriptor things. Deal with it (r).
# Keep a trace of the old stdout, because setup() is just toooooooooo verbose when succeed
stdout_orig = sys.stdout
stderr_orig = sys.stderr
stdout_catched = StringIO()
stderr_redirect_path = '/tmp/stderr.opsbro.tmp' if os.name != 'nt' else r'c:\stderr.opsbro.tmp'
stderr_redirect = None
stderr_orig_bkp = None


def hook_stdout():
    global stderr_redirect
    # Do not hook if we are uploading to pypi
    if not allow_black_magic:
        return
    sys.stdout = stdout_catched
    sys.stderr = stdout_catched
    # Also hook raw stderr
    stderr_redirect = open(stderr_redirect_path, 'w')
    os.dup2(stderr_redirect.fileno(), 2)


# Unhook stdout, put back fd=0
def unhook_stdout():
    global stderr_redirect
    # For pypi, we did not hook it
    if not allow_black_magic:
        return
    # If we have something in the file descriptor 2, reinject into stderr
    stderr_redirect.close()
    # with open(stderr_redirect_path, 'r') as f:
    #    stdout_catched.write(f.read())
    sys.stdout = stdout_orig
    sys.stderr = stderr_orig


##################################       Parse arguments, especially for pip install arg catched
parser = optparse.OptionParser("%prog [options]", version="%prog ")
parser.add_option('--root', dest="proot", metavar="ROOT", help='Root dir to install, usefull only for packagers')
parser.add_option('--upgrade', '--update', dest="upgrade", action='store_true', help='Only upgrade')
parser.add_option('--install-scripts', dest="install_scripts", help='Path to install the opsbro binary')
parser.add_option('--skip-build', dest="skip_build", action='store_true', help='skipping build')
parser.add_option('-O', type="int", dest="optimize", help='skipping build')
parser.add_option('--record', dest="record", help='File to save writing files. Used by pip install only')
parser.add_option('--single-version-externally-managed', dest="single_version", action='store_true', help='This option is for pip only')

old_error = parser.error


def _error(msg):
    pass


parser.error = _error
opts, args = parser.parse_args()
# reenable the errors for later use
parser.error = old_error

root = opts.proot or ''

##################################       Detect install or Update
prev_version = None
prev_path = ''
# We try to see if we are in a full install or an update process
is_update = False
# Try to import opsbro but not the local one. If available, we are in 
# and upgrade phase, not a classic install
try:
    if '.' in sys.path:
        sys.path.remove('.')
    if os.path.abspath('.') in sys.path:
        sys.path.remove(os.path.abspath('.'))
    if '' in sys.path:
        sys.path.remove('')
    import opsbro as opsbro_test_import
    
    is_update = True
    # Try to guess version
    from opsbro.info import VERSION as prev_version
    
    prev_path = os.path.dirname(opsbro_test_import.__file__)
    del opsbro_test_import
    # But to be sure future opsbro import will load the new one, we need to
    # first hard unload the opsbro modules from python
    # NOTE: this is only ok because we are in the setup.py, don't do this outside this scope!
    all_modules = list(sys.modules.keys())
    for modname in all_modules:
        if modname == 'opsbro' or modname.startswith('opsbro.'):
            del sys.modules[modname]
except ImportError as exp:  # great, first install so
    pass

# Now look at loading the local opsbro lib for version and banner
my_dir = os.path.dirname(os.path.abspath(__file__))
opsbro = imp.load_module('opsbro', *imp.find_module('opsbro', [os.path.realpath(my_dir)]))
from opsbro.info import VERSION, BANNER, TXT_BANNER
from opsbro.log import cprint, is_tty, sprintf, core_logger
from opsbro.misc.bro_quotes import get_quote
from opsbro.systempacketmanager import get_systepacketmgr
from opsbro.cli_display import print_h1
from opsbro.characters import CHARACTERS

systepacketmgr = get_systepacketmgr()

##################################       Only root as it's a global system tool.
if os.name != 'nt' and os.getuid() != 0:
    cprint('Setup must be launched as root.', color='red')
    sys.exit(2)

# By default logger should not print anything
core_logger.setLevel('ERROR')
# By maybe we are in verbose more?
if '-v' in sys.argv or os.environ.get('DEBUG_INSTALL', '0') == '1':
    core_logger.setLevel('DEBUG')

core_logger.debug('SCRIPT: install/update script was call with arguments: %s' % orig_sys_argv)

what = 'Installing' if not is_update else 'Updating'
title = sprintf('%s' % what, color='magenta', end='') + sprintf(' OpsBro to version ', end='') + sprintf('%s' % VERSION, color='magenta', end='')

if allow_black_magic:
    print_h1(title, raw_title=False)

##################################       Start to print to the user
if allow_black_magic:
    # If we have a real tty, we can print the delicious banner with lot of BRO
    if is_tty():
        cprint(BANNER)
    else:  # ok you are poor, just got some ascii art then
        cprint(TXT_BANNER)
    
    # Also print a Bro quote
    quote, from_film = get_quote()
    cprint('  >> %s  (%s)\n' % (quote, from_film), color='grey')
if allow_black_magic:
    if is_update:
        cprint('  Previous OpsBro lib detected on this system:')
        cprint('    * location: ', end='')
        cprint(prev_path, color='blue')
        cprint('    * version : ', end='')
        cprint('%s' % prev_version, color='blue')
        cprint('    * Using the ', end='')
        cprint('update process', color='magenta')
    
    print('')

if '--update' in args or opts.upgrade or '--upgrade' in args:
    if 'update' in args:
        sys.argv.remove('update')
        sys.argv.insert(1, 'install')
    if '--update' in args:
        sys.argv.remove('--update')
    if '--upgrade' in args:
        sys.argv.remove('--upgrade')
    is_update = True

# install: if we are with setupy.py install, or maybe with pip launch (last step)
is_install = False
if not is_update and 'install' in args or is_pip_real_install_step:
    is_install = True

install_scripts = opts.install_scripts or ''

# setup() will warn about unknown parameter we already managed
# to delete them
deleting_args = ['--skip-build']
to_del = []
for a in deleting_args:
    for av in sys.argv:
        if av.startswith(a):
            idx = sys.argv.index(av)
            to_del.append(idx)
            if '=' not in av:
                to_del.append(idx + 1)
to_del.sort()
to_del.reverse()
for idx in to_del:
    sys.argv.pop(idx)

# Force the quiet mode for setup.py (too verbose by default)
if '-v' not in sys.argv and '--quiet' not in sys.argv and '-q' not in sys.argv:
    sys.argv.insert(1, '--quiet')

##################################       Prepare the list of files that will be installed


data_files = []
configuration_files = []

# Define files
if 'win' in sys.platform:
    default_paths = {
        'bin'    : install_scripts or "c:\\opsbro\\bin",
        'var'    : "c:\\opsbro\\var",
        'etc'    : "c:\\opsbro\\etc",
        'log'    : "c:\\opsbro\\var\\log",
        'run'    : "c:\\opsbro\\var",
        'libexec': "c:\\opsbro\\libexec",
    }
    data_files = []
elif 'linux' in sys.platform or 'sunos5' in sys.platform:
    default_paths = {
        'bin'    : install_scripts or "/usr/bin",
        'var'    : "/var/lib/opsbro/",
        'etc'    : "/etc/opsbro",
        'run'    : "/var/run/opsbro",
        'log'    : "/var/log/opsbro",
        'libexec': "/var/lib/opsbro/libexec",
    }
    data_files = [
        (
            os.path.join('/etc', 'init.d'),
            ['init.d/opsbro']
        )
    ]
elif 'bsd' in sys.platform or 'dragonfly' in sys.platform:
    default_paths = {
        'bin'    : install_scripts or "/usr/local/bin",
        'var'    : "/usr/local/libexec/opsbro",
        'etc'    : "/usr/local/etc/opsbro",
        'run'    : "/var/run/opsbro",
        'log'    : "/var/log/opsbro",
        'libexec': "/usr/local/libexec/opsbro/plugins",
    }
    data_files = [
        (
            '/usr/local/etc/rc.d',
            ['bin/rc.d/opsbro']
        )
    ]
else:
    raise Exception("Unsupported platform, sorry")

# Beware to install scripts in the bin dir
# compute scripts
scripts = [s for s in glob('bin/opsbro*') if not s.endswith('.py')]
data_files.append((default_paths['bin'], scripts))


def _get_all_from_directory(dirname, path_key, filter_dir=None):
    rename_patern_string = r"^(%s\/|%s$)" % (dirname, dirname)
    rename_patern = re.compile(rename_patern_string)
    directory = dirname
    if filter_dir:
        directory = os.path.join(dirname, filter_dir)
    for path, subdirs, files in os.walk(directory):
        dest_path = os.path.join(default_paths[path_key], rename_patern.sub("", path))
        # for void directories
        if len(files) == 0:
            configuration_files.append((dest_path, []))
        for name in files:
            configuration_files.append((dest_path, [os.path.join(path, name)]))


if not is_update:
    _get_all_from_directory('etc', 'etc')
    _get_all_from_directory('data', 'var')
else:  # only take core directory for update
    _get_all_from_directory('data', 'var', filter_dir='core-configuration')

# Libexec is always installed
for path, subdirs, files in os.walk('libexec'):
    for name in files:
        data_files.append((os.path.join(default_paths['libexec'], re.sub(r"^(libexec\/|libexec$)", "", path)), [os.path.join(path, name)]))

data_files.append((default_paths['run'], []))
data_files.append((default_paths['log'], []))

# Clean data files from all ~ emacs files :)
nd = []
for (r, files) in data_files:
    nd.append((r, [p for p in files if not p.endswith('~')]))
data_files = nd

not_allowed_options = ['--upgrade', '--update']
for o in not_allowed_options:
    if o in sys.argv:
        sys.argv.remove(o)

##################################       Look at prerequites, and if possible fix them with the system package instead of pip

if allow_black_magic:
    print('')
    title = 'Checking prerequites ' + sprintf('(1/3)', color='magenta', end='')
    print_h1(title, raw_title=True)

# Maybe we won't be able to setup with packages, if so, switch to pip :(
install_from_pip = []

# Python 3 and 2 have differents packages
if PY3:
    mod_need = {
        'jinja2': {
            'packages': {
                'debian'       : 'python3-jinja2',
                'ubuntu'       : 'python3-jinja2',
                'amazon-linux' : 'python3-jinja2',
                'amazon-linux2': 'python3-jinja2',
                'centos'       : 'python3-jinja2',
                'redhat'       : 'python3-jinja2',
                'oracle-linux' : 'python3-jinja2',
                'fedora'       : 'python3-jinja2',
                'opensuse'     : 'python3-Jinja2',
                'alpine'       : 'py3-jinja2',
            }
        },
        'Crypto': {
            'packages': {
                'debian'       : 'python3-crypto',
                'ubuntu'       : 'python3-crypto',
                'amazon-linux' : 'python3-crypto',
                'amazon-linux2': 'python3-crypto',
                'centos'       : 'python3-crypto',
                'redhat'       : 'python3-crypto',
                'oracle-linux' : 'python3-crypto',
                'fedora'       : 'python3-crypto',
                'opensuse'     : 'python3-pycrypto',
                'alpine'       : 'py3-crypto',
            }
        },
    }
else:
    mod_need = {
        'jinja2': {
            'packages': {
                'debian'       : 'python-jinja2',
                'ubuntu'       : 'python-jinja2',
                'amazon-linux' : 'python-jinja2',
                'amazon-linux2': 'python-jinja2',
                'centos'       : 'python-jinja2',
                'redhat'       : 'python-jinja2',
                'oracle-linux' : 'python-jinja2',
                'fedora'       : 'python-jinja2',
                'opensuse'     : 'python-Jinja2',
                'alpine'       : 'py-jinja2',
            }
        },
        'Crypto': {
            'packages': {
                'debian'       : 'python-crypto',
                'ubuntu'       : 'python-crypto',
                'amazon-linux' : 'python-crypto',
                'amazon-linux2': 'python-crypto',
                'centos'       : 'python-crypto',
                'redhat'       : 'python-crypto',
                'oracle-linux' : 'python-crypto',
                'fedora'       : 'python-crypto',
                'opensuse'     : 'python-pycrypto',
                'alpine'       : 'py-crypto',
            }
        },
    }

# Some distro have another name for python-setuptools, so list here only exceptions
setuptools_package_exceptions = {
    'alpine'       : 'py-setuptools',
    'amazon-linux' : 'python27-setuptools',
    'amazon-linux2': 'python2-setuptools',
}


# Centos 7.0 and 7.1 have issues to access to the epel release (due to certificates)
# and I don't find how to fix unless remove the https access to it
# if someone have a better solution, with only packages update, I take :)
def _fix_centos_7_epel_no_https():
    epel = '/etc/yum.repos.d/epel.repo'
    if os.path.exists(epel):
        with open(epel, 'r') as f:
            lines = f.readlines()
        # sed 'mirrorlist=https:' into 'mirrorlist=http:'
        # and mirrorlist=https: into mirrorlist=https: (centos 6)
        new_file = ''.join([line.replace('metalink=https:', 'metalink=http:').replace('mirrorlist=https:', 'mirrorlist=http:') for line in lines])
        with open(epel, 'w') as f:
            f.write(new_file)


# Some distro have specific dependencies
distro_prerequites = {
    'alpine': [{'package_name': 'musl-dev'}],  # monotonic clock
    'centos': [
        {'package_name': 'libgomp'},  # monotonic clock
        {'package_name': 'nss', 'only_for': ['6.6', '6.7', '7.0', '7.1'], 'force_update': True},  # force update of nss for connect to up to date HTTPS, especialy epel
        {'package_name': 'epel-release', 'only_for': ['6.7', '7.0', '7.1'], 'post_fix': _fix_centos_7_epel_no_https},  # need for leveldb, and post_fix is need for 6.7
        {'package_name': 'leveldb', 'only_for': ['7.0', '7.1']},  # sqlite on old centos is broken
    ],
}

# If we are uploading to pypi, we just don't want to install/update packages here
if not allow_black_magic:
    mod_need.clear()

# We will have to look in which distro we are
is_managed_system = systepacketmgr.is_managed_system()
system_distro, system_distroversion, _ = systepacketmgr.get_distro()

# Hack for debian & centos 6 that is not configure to access leveldb on pypi because pypi did remove http (no S) on november 2017.
# great....
additionnal_pypi_repos = []
if allow_black_magic:
    additionnal_pypi_repos.append('https://pypi.python.org/pypi/leveldb/')

if allow_black_magic:
    if is_managed_system:
        cprint(' * Your system ', end='')
        cprint('%s (version %s) ' % (system_distro, system_distroversion), color='magenta', end='')
        cprint(u'is managed by this installer: ', end='')
        cprint(CHARACTERS.check, color='green')
        cprint('   - it will be able to use system package manager to install dependencies.', color='grey')
    else:
        cprint(" * ", end='')
        cprint("%s NOTICE" % CHARACTERS.double_exclamation, color='yellow', end='')
        cprint(": your system ", end='')
        cprint('(%s - %s) ' % (system_distro, system_distroversion), color='magenta', end='')
        cprint('is not a managed/tested system:')
        cprint("   - it won't use the package system to install dependencies")
        cprint("   - and so it will use the python pip dependency system instead (internet connection is need).")

for (m, d) in mod_need.items():
    cprint(' * Checking dependency for ', end='')
    cprint('%-20s' % m, color='blue', end='')
    cprint(' : ', end='')
    sys.stdout.flush()
    try:
        __import__(m)
        cprint('%s' % CHARACTERS.check, color='green')
    except ImportError:
        cprint('MISSING', color='cyan')
        packages = d['packages']
        to_install = packages.get(system_distro, '')
        pip_failback = d.get('failback_pip', m)
        if not to_install:
            cprint('   - Cannot find valid packages from system packages on this distribution for the module %s, will be installed by the python pip system instead (need an internet connection)' % m, color='yellow')
            install_from_pip.append(pip_failback)
        else:
            if isinstance(to_install, basestring):
                to_install = [to_install]
            for pkg in to_install:
                cprint('   - Trying to install the package ', color='grey', end='')
                cprint('%-20s' % pkg, color='blue', end='')
                cprint(' from system packages  : ', color='grey', end='')
                sys.stdout.flush()
                try:
                    systepacketmgr.update_or_install(pkg)
                    cprint('%s' % CHARACTERS.check, color='green')
                    # __import__(m)
                except Exception as exp:
                    cprint('(missing in package)', color='cyan')
                    cprint('   - cannot install the package from the system. Switching to an installation based on the python pip system (need an internet connection)', color='grey')
                    _prefix = '      | '
                    cprint('\n'.join(['%s%s' % (_prefix, s) for s in str(exp).splitlines()]), color='grey')
                    
                    install_from_pip.append(pip_failback)

if allow_black_magic:
    distro_specific_packages = distro_prerequites.get(system_distro, [])
    if len(distro_specific_packages) >= 1:
        cprint(' * This OS have specific prerequites:')
    for package in distro_specific_packages:
        package_name = package.get('package_name')
        only_for = package.get('only_for', [])
        # Maybe this package is only for specific versions, like old centos 7 versions
        if len(only_for) != 0:
            match_version = False
            for only_for_version in only_for:
                if system_distroversion.startswith(only_for_version):
                    match_version = True
            if not match_version:
                continue
        force_update = package.get('force_update', False)  # should be updated even if already installed
        post_fix = package.get('post_fix', None)  # function called AFTER the package installation, to fix something
        cprint('   - Prerequite for ', color='grey', end='')
        cprint(system_distro, color='magenta', end='')
        cprint(' : ', color='grey', end='')
        cprint('%-20s' % package_name, color='blue', end='')
        cprint('       from system packages  : ', color='grey', end='')
        sys.stdout.flush()
        try:
            if not systepacketmgr.has_package(package_name) or force_update:
                systepacketmgr.update_or_install(package_name)
                if post_fix:
                    post_fix()
            cprint('%s' % CHARACTERS.check, color='green')
        except Exception as exp:
            cprint('   - ERROR: cannot install the prerequite %s from the system. Please install it manually' % package_name, color='red')
            sys.exit(2)

# windows black magic: we ned pywin32
if os.name == 'nt':
    try:
        import win32api
    except ImportError:
        # No win32api, try to install it, but setup() seems to fail, so call pip for this
        from opsbro.util import exec_command
        
        cprint('   - Prerequite for ', color='grey', end='')
        cprint(system_distro, color='magenta', end='')
        cprint(' : ', color='grey', end='')
        cprint('%-20s' % 'pyiwin32', color='blue', end='')
        cprint('       from pypi  : ', color='grey', end='')
        sys.stdout.flush()
        
        python_exe = os.path.abspath(sys.executable)
        
        # We need both pyiwin32 & pywin32 to works
        # But lastest pywin32 on pypi do not support 3.4, cannot install in automagic
        if PY3 and sys.version_info.minor == 4:  # == 3.4
            cprint('ERROR: the python 3.4 is not managed under windows for automatic installaiton, please install pywin32 first (no more available on pypi for this python version).')
            sys.exit(2)
        for windows_package in ('pypiwin32', 'pywin32'):
            pip_install_command = '%s -m pip install --only-binary %s %s' % (python_exe, windows_package, windows_package)
            try:
                rc, stdout, stderr = exec_command(pip_install_command)
            except Exception as exp:
                cprint('ERROR: cannot install %s: %s' % (windows_package, exp), color='red')
                sys.exit(2)
            if rc != 0:
                cprint('ERROR: cannot install %s: %s' % (windows_package, stdout + stderr), color='red')
                sys.exit(2)
        
        # Now need also to run the python Scripts\pywin32_postinstall.py -install script to register DLL. (I love windows...)
        dll_script = os.path.join(os.path.dirname(python_exe), 'Scripts', 'pywin32_postinstall.py')
        if not os.path.exists(dll_script):
            cprint('ERROR: the pywin32 script to register the DLL is missing. Please install pywin32 manually', color='red')
            sys.exit(2)
        
        dll_registering = '%s %s -install' % (python_exe, dll_script)
        try:
            rc, stdout, stderr = exec_command(dll_registering)
        except Exception as exp:
            cprint('ERROR: cannot install pyiwin32 dlls: %s' % exp, color='red')
            sys.exit(2)
        if rc != 0:
            cprint('ERROR: cannot install pyiwin32dlls: %s' % (stdout + stderr))
            sys.exit(2)
        cprint('%s' % CHARACTERS.check, color='green')

# Remove duplicate from pip install
install_from_pip = set(install_from_pip)

# if we are uploading to pypi, we don't want to have dependencies, I don't want pip to do black magic. I already do black magic.
if not allow_black_magic:
    install_from_pip = set()

# HACK: debian 6 do not allow any more pypi install, sorry :'(
if system_distro == 'debian' and system_distroversion.startswith('6.'):
    install_from_pip = set()

# Try to import setup tools, and if not, switch to
try:
    from setuptools import setup, find_packages
except ImportError:
    try:
        cprint(' * You are missing the python setuptools, trying to install it with system package:', end='')
        sys.stdout.flush()
        default_setuptools_pkg = 'python-setuptools'
        if PY3:
            default_setuptools_pkg = 'python3-setuptools'
        package_name = setuptools_package_exceptions.get(system_distro, default_setuptools_pkg)
        systepacketmgr.install_package(package_name)
        cprint(' %s' % CHARACTERS.check, color='green')
        from setuptools import setup, find_packages
    except Exception as exp:
        cprint('Cannot install python setuptools from system (%s). Cannot continue the installation. Please install python-setuptools before re-run the installation.' % exp, color='red')
        sys.exit(2)

print('\n')
##################################       Go install the python part
if allow_black_magic:
    title = 'Python lib installation ' + sprintf('(2/3)', color='magenta', end='')
    print_h1(title, raw_title=True)
    
    if install_from_pip:
        cprint('  * %s packages will be installed from Pypi (%s)' % (len(install_from_pip), ', '.join(install_from_pip)))
    
    cprint('  * %s opsbro python lib in progress...' % what, end='')
sys.stdout.flush()

hook_stdout()

setup_phase_is_done = False


def print_fail_setup(exp=''):
    if setup_phase_is_done:
        return
    unhook_stdout()
    cprint('\nERROR: fail to setup opsbro: (%s)' % exp, color='red')
    cprint(stdout_catched.getvalue())
    with open(stderr_redirect_path, 'r') as f:
        _prefix = '      | '
        cprint('Python setuptools call fail:\n%s' % ('\n'.join(['%s%s' % (_prefix, s) for s in f.read().splitlines()])), color='red')
    sys.exit(2)


atexit.register(print_fail_setup)

try:
    setup(
        name="opsbro",
        version=VERSION,
        packages=find_packages(),
        package_data={'': package_data},
        description="OpsBro is a service discovery tool",
        long_description=read('README.md'),
        author="Gabes Jean",
        author_email="naparuba@gmail.com",
        license="MIT",
        url="http://opsbro.io",
        zip_safe=False,
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: MIT License',
            'Operating System :: MacOS :: MacOS X',
            'Operating System :: Microsoft :: Windows',
            'Operating System :: POSIX',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2 :: Only',
            'Topic :: System :: Monitoring',
            'Topic :: System :: Networking :: Monitoring',
            'Topic :: System :: Distributed Computing',
        ],
        install_requires=[install_from_pip],
        # data_files=data_files,
        # include_package_data=True,  # we need to let setup() install data files, becwause we must give it AND say it's ok to install....
        # TODO: add some more black magic here! I really hate python packaging!
        
        # Maybe some system need specific packages address on pypi, like add httpS on debian 6 :'(
        dependency_links=additionnal_pypi_repos,
    )
except Exception as exp:
    print_fail_setup(exp)
    sys.exit(2)

# don't print something at exit now
setup_phase_is_done = True

# We did finish the setup, and we did succeed, so we can put the result into a log, we don't fucking care about
# printing it to everyone unless we want to fear them
unhook_stdout()

if allow_black_magic:
    cprint('  %s' % CHARACTERS.check, color='green')

installation_log = '/tmp/opsbro.setup.log' if os.name != 'nt' else r'c:\opsbro.setup.log'
with open(installation_log, 'w') as f:
    f.write(stdout_catched.getvalue())
    if allow_black_magic:
        cprint('   - Raw python setup lib (and possible dependencies) installation log at: %s' % installation_log, color='grey')
        f = open(installation_log)
        cprint(f.read())
        f.close()

##################################       Install init.d script, the daemon script and bash completion part
if allow_black_magic:
    print('\n')
    title = 'Utility script installation ' + sprintf('(3/3)', color='magenta', end='')
    print_h1(title, raw_title=True)


# Just a print with aligned test over : OK
def __print_sub_install_part(p):
    if allow_black_magic:
        cprint('   - %-40s :' % p, color='grey', end='')
        cprint(' %s' % CHARACTERS.check, color='green')


def __do_install_files(lst):
    # * dir : dest_directory
    # * lfiles : local files in this archive
    for (dir, lfiles) in lst:
        # Be sute the directory do exist
        if not os.path.exists(dir):
            # ==> mkdir -p
            core_logger.debug('The directory %s is missing, creating it' % dir)
            os.makedirs(dir)
        for lfile in lfiles:
            lfile_name = os.path.basename(lfile)
            destination = os.path.join(dir, lfile_name)
            core_logger.debug("Copying local file %s into %s" % (lfile, destination))
            shutil.copy2(lfile, destination)


# Always install standard directories (log, run, etc)
if allow_black_magic:
    __do_install_files(data_files)
    __print_sub_install_part('OpsBro scripts & directories')
    
    # Also change the rights of the opsbro- scripts
    for s in scripts:
        bs = os.path.basename(s)
        _chmodplusx(os.path.join(default_paths['bin'], bs))
    __print_sub_install_part('Check daemon file rights')
    _chmodplusx(default_paths['libexec'])
    
    # If not exists, won't raise an error there
    _chmodplusx('/etc/init.d/opsbro')
    __print_sub_install_part('Check init.d script execution rights')

# if root is set, it's for package, so NO chown
# if pypi upload, don't need this
if not root and is_install and allow_black_magic:
    cprint(' * Installing data & scripts (sample configuration, init.d, daemon, bash completion)')
    
    # Install configuration, packs
    __do_install_files(configuration_files)
    __print_sub_install_part('Sample configuration & core packs')
    
    # Also install the bash completion part if there is such a directory
    bash_completion_dir = '/etc/bash_completion.d/'
    if os.path.exists(bash_completion_dir):
        dest = os.path.join(bash_completion_dir, 'opsbro')
        shutil.copy('bash_completion/opsbro', dest)
        _chmodplusx(dest)
        __print_sub_install_part('bash completion rule')

if not root and is_update and allow_black_magic:
    cprint(' * Updating core configuration files')
    __print_sub_install_part('Core packs')
    core_configuration_dir = os.path.join(default_paths['var'], 'core-configuration')
    shutil.rmtree(core_configuration_dir)
    __do_install_files(configuration_files)

if allow_black_magic:
    print('')
    print_h1('End', raw_title=True)
    cprint('OpsBro ', end='')
    cprint(what, color='magenta', end='')
    cprint(' : ', end='')
    cprint(' %s' % CHARACTERS.check, color='green')
    
    cprint('  %s Notes: ' % CHARACTERS.corner_bottom_left, color='grey')
    cprint('     - you can now start your daemon with:  service opsbro start', color='grey')
    cprint('     - you can look at all available with:  opsbro -h', color='grey')
