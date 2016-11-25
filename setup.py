#!/usr/bin/python

# -*- coding: utf-8 -*-

import os
import sys
import re
import stat
import optparse
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
        print "warn: _chmodplusx missing dir", d
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


parser = optparse.OptionParser(
    "%prog [options]", version="%prog ")
parser.add_option('--root',
                  dest="proot", metavar="ROOT",
                  help='Root dir to install, usefull only for packagers')
parser.add_option('--upgrade', '--update',
                  dest="upgrade", action='store_true',
                  help='Only upgrade')
parser.add_option('--install-scripts',
                  dest="install_scripts",
                  help='Path to install the kunai binary')
parser.add_option('--skip-build',
                  dest="skip_build", action='store_true',
                  help='skipping build')
parser.add_option('-O', type="int",
                  dest="optimize",
                  help='skipping build')
parser.add_option('--record',
                  dest="record",
                  help='File to save writing files. Used by pip install only')
parser.add_option('--single-version-externally-managed',
                  dest="single_version", action='store_true',
                  help='This option is for pip only')

old_error = parser.error


def _error(msg):
    print 'Parser error', msg


parser.error = _error
opts, args = parser.parse_args()
# reenable the errors for later use
parser.error = old_error

root = opts.proot or ''

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
    import kunai
    
    is_update = True
    print "Previous Kunai lib detected at (%s)" % kunai.__file__
except ImportError:  # great, first install so
    pass

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

required_pkgs = ['leveldb', 'jinja2', 'pycurl', 'requests', 'cherrypy', 'crypto', 'rsa', 'pyasn1']
setup(
    name="Kunai",
    version="0.9-beta1",
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
    install_requires=[required_pkgs],
    
    extras_require={
        'setproctitle': ['setproctitle']
    },
    data_files=data_files,
)

# if root is set, it's for package, so NO chown
if not root and is_install:
    # Also change the rights of the kunai- scripts
    for s in scripts:
        bs = os.path.basename(s)
        _chmodplusx(os.path.join(default_paths['bin'], bs))
    _chmodplusx(default_paths['libexec'])
    
    # If not exists, won't raise an error there
    _chmodplusx('/etc/init.d/kunai')

mod_need = ['requests', 'cherrypy', 'leveldb', 'jinja2', 'rsa', 'pyasn1']
for m in mod_need:
    try:
        __import__(m)
    except ImportError:
        print('\033[93mWarning: cannot import module %s. You must install if before launch the kunai deamon \033[0m' % m)

print "\033[92mKunai install: OK\033[0m"
