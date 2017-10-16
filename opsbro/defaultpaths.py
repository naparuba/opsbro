import os

if os.name == "nt":
    DEFAULT_DATA_DIR = r'c:\opsbro\data'
    DEFAULT_LOG_DIR = r'c:\opsbro\log'
    DEFAULT_LOCK_PATH = r'c:\opsbro\run\opsbro.lock'
    DEFAULT_LIBEXEC_DIR = r'c:\opsbro\libexec'
    DEFAULT_CFG_DIR = r'c:\opsbro\etc'
    DEFAULT_SOCK_PATH = r'c:\opsbro\run\opsbro.sock'
else:
    DEFAULT_DATA_DIR = r'/var/lib/opsbro'
    DEFAULT_LOG_DIR = r'/var/log/opsbro'
    DEFAULT_LOCK_PATH = r'/var/run/opsbro.lock'
    DEFAULT_LIBEXEC_DIR = r'/var/lib/opsbro/libexec'
    DEFAULT_CFG_DIR = r'/etc/opsbro'
    DEFAULT_SOCK_PATH = r'/var/lib/opsbro/opsbro.sock'

DEFAULT_CFG_FILE = os.path.join(DEFAULT_CFG_DIR, 'agent.yml')


# If the user want to run without install, we will change the installations PATH
# from the main root dirs
def remap_from_install_dir():
    global DEFAULT_DATA_DIR, DEFAULT_LOG_DIR, DEFAULT_LOCK_PATH, DEFAULT_LOCK_PATH, DEFAULT_CFG_FILE, DEFAULT_CFG_DIR, DEFAULT_SOCK_PATH
    my_dir = os.path.dirname(__file__)
    install_root = os.path.dirname(my_dir)
    
    DEFAULT_DATA_DIR = os.path.join(install_root, 'data')
    DEFAULT_LOG_DIR = os.path.join(install_root, 'log')
    DEFAULT_LOCK_PATH = os.path.join(install_root, 'log', 'opsbro.lock')
    DEFAULT_CFG_DIR = os.path.join(install_root, 'etc')
    DEFAULT_CFG_FILE = os.path.join(DEFAULT_CFG_DIR, 'agent.yml')
    DEFAULT_SOCK_PATH = os.path.join(DEFAULT_DATA_DIR, 'opsbro.sock')
