import os

if os.name == "nt":
    DEFAULT_DATA_DIR = r'c:\opsbro\data'
    DEFAULT_LOG_DIR = r'c:\opsbro\log'
    DEFAULT_LOCK_PATH = r'c:\opsbro\run\opsbro.lock'
    DEFAULT_LIBEXEC_DIR = r'c:\opsbro\libexec'
    DEFAULT_CFG_DIR = r'c:\opsbro\etc\local.json'
else:
    DEFAULT_DATA_DIR = r'/var/lib/opsbro'
    DEFAULT_LOG_DIR = r'/var/log/opsbro'
    DEFAULT_LOCK_PATH = r'/var/run/opsbro.lock'
    DEFAULT_LIBEXEC_DIR = r'/var/lib/opsbro/libexec'
    DEFAULT_CFG_DIR = r'/etc/opsbro'

DEFAULT_CFG_FILE = os.path.join(DEFAULT_CFG_DIR, 'local.json')
