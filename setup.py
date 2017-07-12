#!/usr/bin/python

# -*- coding: utf-8 -*-

import os
import sys
import re
import stat
import optparse
import shutil
import imp
from glob import glob

try:
    from setuptools import setup
    from setuptools import find_packages
except:
    sys.exit("Error: missing python-setuptools library")

# will fail under 1.5 python version, but if really you have such a version in
# prod you are a morron and we can't help you
python_version = sys.version_info
if python_version < (2, 6):
    sys.exit("Kunai require as a minimum Python 2.6, sorry")
elif python_version >= (3,):
    sys.exit("Kunai is not yet compatible with Python 3.x, sorry")

package_data = ['*.py']


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


parser = optparse.OptionParser("%prog [options]", version="%prog ")
parser.add_option('--root', dest="proot", metavar="ROOT", help='Root dir to install, usefull only for packagers')
parser.add_option('--upgrade', '--update', dest="upgrade", action='store_true', help='Only upgrade')
parser.add_option('--install-scripts', dest="install_scripts", help='Path to install the kunai binary')
parser.add_option('--skip-build', dest="skip_build", action='store_true', help='skipping build')
parser.add_option('-O', type="int", dest="optimize", help='skipping build')
parser.add_option('--record', dest="record", help='File to save writing files. Used by pip install only')
parser.add_option('--single-version-externally-managed', dest="single_version", action='store_true', help='This option is for pip only')

old_error = parser.error


def _error(msg):
    # print 'Parser error', msg
    pass


parser.error = _error
opts, args = parser.parse_args()
# reenable the errors for later use
parser.error = old_error

root = opts.proot or ''

prev_version = None
prev_path = ''
# We try to see if we are in a full install or an update process
is_update = False
# Try to import kunai but not the local one. If available, we are in 
# and upgrade phase, not a classic install
try:
    if '.' in sys.path:
        sys.path.remove('.')
    if os.path.abspath('.') in sys.path:
        sys.path.remove(os.path.abspath('.'))
    if '' in sys.path:
        sys.path.remove('')
    import kunai as kunai_test_import
    
    is_update = True
    # Try to guess version
    from kunai.info import VERSION as prev_version
    
    prev_path = os.path.dirname(kunai_test_import.__file__)
    del kunai_test_import
except ImportError, exp:  # great, first install so
    print "No previous kunai installation found: %s" % exp

# Now look at loading the local kunai lib for version and banner
my_dir = os.path.dirname(os.path.abspath(__file__))
kunai = imp.load_module('kunai', *imp.find_module('kunai', [os.path.realpath(my_dir)]))
from kunai.info import VERSION, BANNER
from kunai.log import cprint
from kunai.systempacketmanager import systepacketmgr


if os.getuid() != 0:
    cprint('Setup must be launched as root.', color='red')
    sys.exit(2)

cprint(BANNER, color='green')

what = 'Installing' if not is_update else 'Updating'
cprint('%s   ' % ('*' * 20), end='')
cprint('%s' % what, color='magenta', end='')
cprint(' to version ', end='')
cprint('%s' % VERSION, color='magenta', end='')
cprint('     %s' % ('*' * 20))

if is_update:
    cprint('Previous Kunai lib detected on this system (location:', end='')
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
    print "Kunai lib update only"
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

# compute scripts
scripts = [s for s in glob('bin/kunai*') if not s.endswith('.py')]

# Define files
if 'win' in sys.platform:
    default_paths = {
        'bin'    : install_scripts or "c:\\kunai\\bin",
        'var'    : "c:\\kunai\\var",
        'etc'    : "c:\\kunai\\etc",
        'log'    : "c:\\kunai\\var\\log",
        'run'    : "c:\\kunai\\var",
        'libexec': "c:\\kunai\\libexec",
    }
    data_files = []
elif 'linux' in sys.platform or 'sunos5' in sys.platform:
    default_paths = {
        'bin'    : install_scripts or "/usr/bin",
        'var'    : "/var/lib/kunai/",
        'etc'    : "/etc/kunai",
        'run'    : "/var/run/kunai",
        'log'    : "/var/log/kunai",
        'libexec': "/var/lib/kunai/libexec",
    }
    data_files = [
        (
            os.path.join('/etc', 'init.d'),
            ['init.d/kunai']
        )
    ]

elif 'bsd' in sys.platform or 'dragonfly' in sys.platform:
    default_paths = {
        'bin'    : install_scripts or "/usr/local/bin",
        'var'    : "/usr/local/libexec/kunai",
        'etc'    : "/usr/local/etc/kunai",
        'run'    : "/var/run/kunai",
        'log'    : "/var/log/kunai",
        'libexec': "/usr/local/libexec/kunai/plugins",
    }
    data_files = [
        (
            '/usr/local/etc/rc.d',
            ['bin/rc.d/kunai']
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
            data_files.append((os.path.join(default_paths['var'], re.sub(r"^(data\/|data$)", "", path)),
                               [os.path.join(path, name)]))

# Libexec is always installed
for path, subdirs, files in os.walk('libexec'):
    for name in files:
        data_files.append((os.path.join(default_paths['libexec'], re.sub(r"^(libexec\/|libexec$)", "", path)),
                           [os.path.join(path, name)]))

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

cprint('# %-30s  (1/3)' % 'Checking prerequites')
mod_need = ['requests', 'cherrypy', 'leveldb', 'jinja2', 'rsa', 'pyasn1', 'pycurl', 'crypto']
# leveldb and setproctitle are not available on windows
if os.name != 'nt':
    mod_need.append('leveldb')
    mod_need.append('setproctitle')

for m in mod_need:
    try:
        __import__(m)
    except ImportError:
        cprint('Warning: cannot import module %s. You must install if before launch the kunai deamon' % m, color='yellow')


cprint('\n\n# %-30s  (2/3)' % 'Python lib installation')
cprint('%s kunai python lib in progress...' % what, end='')
sys.stdout.flush()


setup(
    name="kunai",
    version=VERSION,
    packages=find_packages(),
    package_data={'': package_data},
    description="Kunai is a service discovery tool",
    long_description=read('README.md'),
    author="Gabes Jean",
    author_email="naparuba@gmail.com",
    license="MIT",
    url="http://kunai.io",
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
    data_files=data_files,
)

cprint('  OK', color='green')


# Just a print with aligned test over : OK
def __print_sub_install_part(p):
    cprint('  * %-30s :' % p, end='')
    cprint(' OK', color='green')


cprint('\n\n# %-30s  (3/3)' % 'Utility script installation')

# if root is set, it's for package, so NO chown
if not root and is_install:
    cprint('Installing utility scripts (init.d, daemon, bash completion, etc)')
    # Also change the rights of the kunai- scripts
    for s in scripts:
        bs = os.path.basename(s)
        _chmodplusx(os.path.join(default_paths['bin'], bs))
    __print_sub_install_part('daemon')
    _chmodplusx(default_paths['libexec'])
    
    # If not exists, won't raise an error there
    _chmodplusx('/etc/init.d/kunai')
    __print_sub_install_part('init.d script')
    
    # Also install the bash completion part if there is such a directory
    bash_completion_dir = '/etc/bash_completion.d/'
    if os.path.exists(bash_completion_dir):
        dest = os.path.join(bash_completion_dir, 'kunai')
        shutil.copy('bash_completion/kunai', dest)
        _chmodplusx(dest)
        __print_sub_install_part('bash completion rule')

print ''
cprint('*' * 40)
cprint('Kunai ', end='')
cprint(what, color='magenta', end='')
cprint(' : ', end='')
cprint(' OK', color='green')
