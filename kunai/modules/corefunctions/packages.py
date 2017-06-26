import time
import os

try:
    import apt
except ImportError:
    apt = None

try:
    import yum
except ImportError:
    yum = None

from kunai.evaluater import export_evaluater_function
from kunai.log import logger

deb_cache = None
deb_cache_update_time = 0
DEB_CACHE_MAX_AGE = 60  # if we cannot look at dpkg data age, allow a max cache of 60s to get a new apt update from disk
DPKG_CACHE_PATH = '/var/cache/apt/pkgcache.bin'
dpkg_cache_last_modification_epoch = 0.0

yumbase = None


@export_evaluater_function
def has_package(package):
    """**has_package(package)** -> return True if the package is installed on the system, False otherwise.

 * package: (string) name of the package to check for.

<code>
    Example:
        has_package('postfix')
    Returns:
        False
</code>
    """
    global deb_cache, deb_cache_update_time, dpkg_cache_last_modification_epoch
    global yumbase
    
    if apt:
        t0 = time.time()
        if not deb_cache:
            deb_cache = apt.Cache()
            deb_cache_update_time = int(time.time())
        else:  # ok already existing, look if we should update it
            # because if there was a package installed, it's no more in cache
            need_reload = False
            if os.path.exists(DPKG_CACHE_PATH):
                last_change = os.stat(DPKG_CACHE_PATH).st_mtime
                if last_change != dpkg_cache_last_modification_epoch:
                    need_reload = True
                    dpkg_cache_last_modification_epoch = last_change
            else:  # ok we cannot look at the dpkg file age, must limit by time
                # the cache is just a memory view, so if too old, need to udpate it
                if deb_cache_update_time < time.time() - DEB_CACHE_MAX_AGE:
                    need_reload = True
            if need_reload:
                deb_cache.open(None)
                deb_cache_update_time = int(time.time())
        b = (package in deb_cache and deb_cache[package].is_installed)
        logger.debug('TIME TO QUERY APT: %.3f' % (time.time() - t0), part='evaluator')
        return b
    if yum:
        if not yumbase:
            yumbase = yum.YumBase()
            yumbase.conf.cache = 1
        return package in (pkg.name for pkg in yumbase.rpmdb.returnPackages())
