#!/usr/bin/python

# -*- coding: utf-8 -*-

import os
import sys
import re
import stat
import optparse
import shutil
import imp
from cStringIO import StringIO
from glob import glob
import atexit

# will fail under 2.5 python version, but if really you have such a version in
# prod you are a morron and we can't help you
python_version = sys.version_info
if python_version < (2, 6):
    sys.exit("OpsBro require as a minimum Python 2.6, sorry")
elif python_version >= (3,):
    sys.exit("OpsBro is not yet compatible with Python 3.x, sorry")

package_data = ['*.py']


##################################       Utility functions for files
# helper function to read the README file
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


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
stderr_redirect_path = '/tmp/stderr.opsbro.tmp'
stderr_redirect = None
stderr_orig_bkp = None


def hook_stdout():
    global stderr_redirect
    sys.stdout = stdout_catched
    sys.stderr = stdout_catched
    # Also hook raw stderr
    stderr_redirect = open(stderr_redirect_path, 'w')
    os.dup2(stderr_redirect.fileno(), 2)


# Unhook stdout, put back fd=0
def unhook_stdout():
    global stderr_redirect
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
except ImportError, exp:  # great, first install so
    pass

# Now look at loading the local opsbro lib for version and banner
my_dir = os.path.dirname(os.path.abspath(__file__))
opsbro = imp.load_module('opsbro', *imp.find_module('opsbro', [os.path.realpath(my_dir)]))
from opsbro.info import VERSION, BANNER, TXT_BANNER
from opsbro.log import cprint, is_tty, sprintf
from opsbro.misc.bro_quotes import get_quote
from opsbro.systempacketmanager import systepacketmgr
from opsbro.cli import print_h1
from opsbro.characters import CHARACTERS

##################################       Only root as it's a global system tool.
if os.getuid() != 0:
    cprint('Setup must be launched as root.', color='red')
    sys.exit(2)

what = 'Installing' if not is_update else 'Updating'
title = sprintf('%s' % what, color='magenta', end='') + sprintf(' OpsBro to version ', end='') + sprintf('%s' % VERSION, color='magenta', end='')

print_h1(title, raw_title=False)

##################################       Start to print to the user
# If we have a real tty, we can print the delicious banner with lot of BRO
if is_tty():
    cprint(BANNER)
else:  # ok you are poor, just got some ascii art then
    cprint(TXT_BANNER)

# Also print a Bro quote
quote, from_film = get_quote()
cprint('  >> %s  (%s)\n' % (quote, from_film), color='grey')

if is_update:
    cprint('  Previous OpsBro lib detected on this system (location:', end='')
    cprint(prev_path, color='blue', end='')
    cprint(')(version:', end='')
    cprint('%s' % prev_version, color='blue', end='')
    cprint('), using the ', end='')
    cprint('update process', color='magenta')

print ''

if '--update' in args or opts.upgrade or '--upgrade' in args:
    if 'update' in args:
        sys.argv.remove('update')
        sys.argv.insert(1, 'install')
    if '--update' in args:
        sys.argv.remove('--update')
    if '--upgrade' in args:
        sys.argv.remove('--upgrade')
    is_update = True

is_install = False
if 'install' in args:
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
# compute scripts
scripts = [s for s in glob('bin/opsbro*') if not s.endswith('.py')]

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
    raise "Unsupported platform, sorry"
    data_files = []

# Beware to install scripts in the bin dir
data_files.append((default_paths['bin'], scripts))

if not is_update:
    ## get all files + under-files in etc/ except daemons folder
    for path, subdirs, files in os.walk('etc'):
        # for void directories
        if len(files) == 0:
            data_files.append((os.path.join(default_paths['etc'], re.sub(r"^(etc\/|etc$)", "", path)), []))
        for name in files:
            data_files.append((os.path.join(default_paths['etc'], re.sub(r"^(etc\/|etc$)", "", path)),
                               [os.path.join(path, name)]))
    ## get all files + under-files in etc/ except daemons folder
    for path, subdirs, files in os.walk('data'):
        # for void directories
        if len(files) == 0:
            data_files.append((os.path.join(default_paths['var'], re.sub(r"^(data\/|data$)", "", path)), []))
        for name in files:
            data_files.append((os.path.join(default_paths['var'], re.sub(r"^(data\/|data$)", "", path)), [os.path.join(path, name)]))

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

print ''
title = 'Checking prerequites ' + sprintf('(1/3)', color='magenta', end='')
print_h1(title, raw_title=True)

# Maybe we won't be able to setup with packages, if so, switch to pip :(
install_from_pip = []

mod_need = {
    'requests': {
        'packages': {
            'debian'      : 'python-requests', 'ubuntu': 'python-requests',
            'amazon-linux': 'python27-requests', 'centos': 'python-requests', 'redhat': 'python-requests', 'oracle-linux': 'python-requests', 'fedora': 'python-requests',
        }
    },
    'cherrypy': {  # note: centos: first epel to enable cherrypy get from packages
        'packages'    : {
            'debian'      : 'python-cherrypy3', 'ubuntu': 'python-cherrypy3',
            'amazon-linux': 'python-cherrypy3', 'centos': ['epel-release', 'python-cherrypy'], 'redhat': 'python-cherrypy', 'oracle-linux': 'python-cherrypy', 'fedora': 'python-cherrypy',
        },
        'failback_pip': 'cherrypy==3.2.4',
    },
    'jinja2'  : {
        'packages': {
            'debian'      : 'python-jinja2', 'ubuntu': 'python-jinja2',
            'amazon-linux': 'python-jinja2', 'centos': 'python-jinja2', 'redhat': 'python-jinja2', 'oracle-linux': 'python-jinja2', 'fedora': 'python-jinja2',
        }
    },
    'Crypto'  : {
        'packages': {
            'debian'      : 'python-crypto', 'ubuntu': 'python-crypto',
            'amazon-linux': 'python-crypto', 'centos': 'python-crypto', 'redhat': 'python-crypto', 'oracle-linux': 'python-crypto', 'fedora': 'python-crypto',
        }
    },
}
# leveldb is not available on windows
if os.name != 'nt':
    mod_need['leveldb'] = {
        'packages'    : {
            'debian'      : 'python-leveldb', 'ubuntu': 'python-leveldb',
            'amazon-linux': 'python-leveldb', 'centos': 'python-leveldb', 'redhat': 'python-leveldb', 'oracle-linux': 'python-leveldb', 'fedora': 'python-leveldb',
        },
        'pip_packages': {
            'debian'      : ['build-essential', 'python-dev'], 'ubuntu': ['build-essential', 'python-dev'],
            # NOTE: amazon: no python-devel/python-setuptools, only versionsed packages are available
            'amazon-linux': ['gcc', 'gcc-c++', 'python27-devel', 'libyaml-devel', 'python27-setuptools'], 'centos': ['gcc', 'gcc-c++', 'python-devel', 'libyaml-devel'], 'redhat': ['gcc', 'gcc-c++', 'python-devel', 'libyaml-devel'],
            'oracle-linux': ['gcc', 'gcc-c++', 'python-devel', 'libyaml-devel'], 'fedora': ['gcc', 'gcc-c++', 'python-devel', 'libyaml-devel'],
        },
    }

# We will have to look in which distro we are
is_managed_system = systepacketmgr.is_managed_system()
system_distro, system_distroversion, _ = systepacketmgr.get_distro()
if is_managed_system:
    cprint(' * Your system ', end='')
    cprint('%s (version %s) ' % (system_distro, system_distroversion), color='magenta', end='')
    cprint('is managed by this installer and will be able to use system package manager to install dependencies.')
else:
    cprint(
        " * NOTICE: your system (%s - %s) is not a tested system, it won't use the package system to install dependencies and will use the python pip dependency system instead (internet connection is need)." % (system_distro, system_distroversion))

for (m, d) in mod_need.iteritems():
    cprint(' * checking dependency for ', end='')
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
                    systepacketmgr.install_package(pkg)
                    cprint('%s' % CHARACTERS.check, color='green')
                    # __import__(m)
                except Exception, exp:
                    cprint('(missing in package)', color='cyan')
                    cprint('   - cannot install the package from the system. Switching to an installation based on the python pip system (need an internet connection)', color='grey')
                    _prefix = '      | '
                    cprint('\n'.join(['%s%s' % (_prefix, s) for s in str(exp).splitlines()]), color='grey')
                    
                    install_from_pip.append(pip_failback)
                    all_pip_packages = d.get('pip_packages', {})
                    pip_packages = all_pip_packages.get(system_distro, [])
                    for pip_pkg in pip_packages:
                        try:
                            cprint('   - Install from system package the python lib dependency: ', color='grey', end='')
                            cprint(pip_pkg)
                            systepacketmgr.install_package(pip_pkg)
                        except Exception, exp:
                            cprint('    - WARNING: cannot import python lib dependency: %s : %s' % (pip_pkg, exp))
                            
                            # Remove duplicate from pip install
install_from_pip = set(install_from_pip)

# Try to import setup tools, and if not, switch to
try:
    from setuptools import setup, find_packages
except ImportError:
    try:
        cprint(' * You are missing the python setuptools, trying to install it with system package:', end='')
        sys.stdout.flush()
        systepacketmgr.install_package('python-setuptools')
        cprint(' %s' % CHARACTERS.check, color='green')
        from setuptools import setup, find_packages
    except Exception, exp:
        cprint('Cannot install python setuptools from system (%s). Cannot continue the installation. Please install python-setuptools before re-run the installation.' % exp, color='red')
        sys.exit(2)

print '\n'
##################################       Go install the python part
title = 'Python lib installation ' + sprintf('(2/3)', color='magenta', end='')
print_h1(title, raw_title=True)

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
        data_files=data_files,
    )
except Exception, exp:
    print_fail_setup(exp)
    sys.exit(2)

# don't print something at exit now
setup_phase_is_done = True

# We did finish the setup, and we did succeed, so we can put the result into a log, we don't fucking care about
# printing it to everyone unless we want to fear them
unhook_stdout()

cprint('  %s' % CHARACTERS.check, color='green')

installation_log = '/tmp/opsbro.setup.log'
with open(installation_log, 'w') as f:
    f.write(stdout_catched.getvalue())
    cprint('   - Raw python setup lib (and possible depndencies) installation log at: %s' % installation_log, color='grey')

##################################       Install init.d script, the daemon script and bash completion part
print '\n'
title = 'Utility script installation ' + sprintf('(3/3)', color='magenta', end='')
print_h1(title, raw_title=True)


# Just a print with aligned test over : OK
def __print_sub_install_part(p):
    cprint('   - %-30s :' % p, color='grey', end='')
    cprint(' %s' % CHARACTERS.check, color='green')


# if root is set, it's for package, so NO chown
if not root and is_install:
    cprint(' * Installing utility scripts (init.d, daemon, bash completion, etc)')
    # Also change the rights of the opsbro- scripts
    for s in scripts:
        bs = os.path.basename(s)
        _chmodplusx(os.path.join(default_paths['bin'], bs))
    __print_sub_install_part('daemon')
    _chmodplusx(default_paths['libexec'])
    
    # If not exists, won't raise an error there
    _chmodplusx('/etc/init.d/opsbro')
    __print_sub_install_part('init.d script')
    
    # Also install the bash completion part if there is such a directory
    bash_completion_dir = '/etc/bash_completion.d/'
    if os.path.exists(bash_completion_dir):
        dest = os.path.join(bash_completion_dir, 'opsbro')
        shutil.copy('bash_completion/opsbro', dest)
        _chmodplusx(dest)
        __print_sub_install_part('bash completion rule')

print ''
print_h1('End', raw_title=True)
cprint('OpsBro ', end='')
cprint(what, color='magenta', end='')
cprint(' : ', end='')
cprint(' %s' % CHARACTERS.check, color='green')
