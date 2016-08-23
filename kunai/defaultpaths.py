import os

if os.name == "nt":
    DEFAULT_DATA_DIR = r'c:\kunai\data'
    DEFAULT_LOG_DIR = r'c:\kunai\log'
    DEFAULT_LOCK_PATH = r'c:\kunai\run\kunai.lock'
    DEFAULT_LIBEXEC_DIR = r'c:\kunai\libexec'
    DEFAULT_CFG_DIR = r'c:\kunai\etc\local.json'
else:
    DEFAULT_DATA_DIR = r'/var/lib/kunai'
    DEFAULT_LOG_DIR = r'/var/log/kunai'
    DEFAULT_LOCK_PATH = r'/var/run/kunai.lock'
    DEFAULT_LIBEXEC_DIR = r'/var/lib/kunai/libexec'
    DEFAULT_CFG_DIR = r'/etc/kunai'

DEFAULT_CFG_FILE = os.path.join(DEFAULT_LOG_DIR, 'local.json')
