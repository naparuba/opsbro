import os

from opsbro.collector import Collector
from opsbro.util import unicode_to_bytes

import ctypes
import ctypes.util

try:
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
except Exception:  # windows
    libc = None


class statfs_t(ctypes.Structure):
    """Describes the details about a filesystem.

    f_type:    type of file system (see below)
    f_bsize:   optimal transfer block size
    f_blocks:  total data blocks in file system
    f_bfree:   free blocks in fs
    f_bavail:  free blocks avail to non-superuser
    f_files:   total file nodes in file system
    f_ffree:   free file nodes in fs
    f_fsid:    file system id
    f_namelen: maximum length of filenames
    """
    _fields_ = [
        ("f_type", ctypes.c_long),  # type of file system (see below)
        ("f_bsize", ctypes.c_long),  # optimal transfer block size
        ("f_blocks", ctypes.c_long),  # total data blocks in file system
        ("f_bfree", ctypes.c_long),  # free blocks in fs
        ("f_bavail", ctypes.c_long),  # free blocks avail to non-superuser
        ("f_files", ctypes.c_long),  # total file nodes in file system
        ("f_ffree", ctypes.c_long),  # free file nodes in fs
        ("f_fsid", ctypes.c_int * 2),  # file system id
        ("f_namelen", ctypes.c_long),  # maximum length of filenames
        # statfs_t has a bunch of extra padding, we hopefully guess large enough.
        ("padding", ctypes.c_char * 1024),
    ]


_statfs = libc.statfs
_statfs.argtypes = [ctypes.c_char_p, ctypes.POINTER(statfs_t)]
_statfs.rettype = ctypes.c_int


def statfs(path):
    """The function statfs() returns information about a mounted file system.

    Args:
      path: is the pathname of any file within the mounted file system.

    Returns:
      Returns a statfs_t object.
    """
    buf = statfs_t()
    path = unicode_to_bytes(path)  # python3: need a raw string, not unicode
    err = _statfs(path, ctypes.byref(buf))
    if err == -1:
        errno = ctypes.get_errno()
        raise OSError(errno, '%s path: %r' % (os.strerror(errno), path))
    return buf


_fstatfs = libc.fstatfs
_fstatfs.argtypes = [ctypes.c_int, ctypes.POINTER(statfs_t)]
_fstatfs.rettype = ctypes.c_int


def fstatfs(fd):
    """The fuction fstatfs() returns information about a mounted file ssytem.

    Args:
      fd: A file descriptor.

    Returns:
      Returns a statfs_t object.
    """
    buf = statfs_t()
    fileno = fd.fileno()
    assert fileno
    err = _fstatfs(fileno, ctypes.byref(buf))
    if err == -1:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    return buf


class DiskUsage(Collector):
    not_wish_fs_type = set(['sysfs', 'devtmpfs', 'securityfs',
                            'devpts', 'cgroup', 'pstore', 'configfs',
                            'mqueue', 'hugetlbfs', 'autofs', 'fusectl',
                            'proc', 'smbfs', 'cifs', 'iso9660', 'udf',
                            'nfsv4', 'udev'])
    
    
    def _get_volume_paths(self):
        fs_paths = []
        with open('/etc/mtab', 'r') as f:
            lines = f.readlines()
            for line in lines:
                # /dev/md1 / ext4 rw,relatime,errors=remount-ro 0 0
                device, path, fs_type, _ = line.split(' ', 3)
                if fs_type in self.not_wish_fs_type:
                    continue
                fs_paths.append((path, fs_type))
        return fs_paths
    
    
    @staticmethod
    def _get_and_unduplicate_volume_stats(fs_paths):
        final_fs_details = {}
        for (path, fs_type) in fs_paths:
            details = statfs(path)
            fs_id = (details.f_fsid[0], details.f_fsid[1])
            prev_entry = final_fs_details.get(fs_id, None)
            if prev_entry is None:  # new fs
                final_fs_details[fs_id] = (path, fs_type, details)
            else:
                prev_path, _, _ = prev_entry
                # is our path shorter than the previous?
                if len(path) < len(prev_path):
                    final_fs_details[fs_id] = (path, fs_type, details)
        return final_fs_details
    
    
    def launch(self):
        # logger.debug('getDiskUsage: start')
        
        # logger.debug('getDiskUsage: attempting Popen')
        if os.name == 'nt':
            self.set_not_eligible('This collector is not availabe on windows currently.')
            return False
        
        fs_paths = self._get_volume_paths()
        final_fs_details = self._get_and_unduplicate_volume_stats(fs_paths)
        
        usage_data = {}
        for (path, fs_type, details) in final_fs_details.values():
            d = {}
            self.logger.debug("%s => f_bsize: %s" % (path, details.f_bsize))
            self.logger.debug("%s => f_blocks: total data blocks in file system: %s" % (path, details.f_blocks))
            self.logger.debug("%s => f_bfree: free blocks in fs: %s" % (path, details.f_bfree))
            block_size = details.f_bsize
            total_size = int(details.f_blocks * block_size / (1024.0 * 1024.0))
            free_size = int(details.f_bfree * block_size / (1024.0 * 1024.0))
            used_size = total_size - free_size
            pct_used = round(float(100 * float(used_size) / total_size), 1)
            
            self.logger.debug("%s=> Total size:%s   used:%s  pct:%s" % (path, total_size, used_size, pct_used))
            
            d['total'] = total_size
            d['used'] = used_size
            d['pct_used'] = pct_used
            usage_data[path] = d
        
        return usage_data
