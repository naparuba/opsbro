#!/usr/bin/python2.4
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Lets Python access the Linux statfs and fstatfs methods.

See man statfs for usage.
"""
import os
import time

from opsbro.util import bytes_to_unicode, unicode_to_bytes
import ctypes
import ctypes.util

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)

t0 = time.time()


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
    print('TYPE? %s=>%s' % (path, type(path)))
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


def filesystem(path_or_fd):
    """Get the filesystem type a file/path is on.
  
    Args:
      path_or_fd: A string path or an object which has a fileno function.
  
    Returns:
     A string name of the file system.
    """
    if hasattr(path_or_fd, 'fileno'):
        buf = fstatfs(path_or_fd)
    else:
        buf = statfs(path_or_fd)
    assert buf
    try:
        return f_types[buf.f_type]
    except KeyError:
        return "UNKNOWN"


# Constants for filesystem magic
ADFS_SUPER_MAGIC = 0xadf5
AFFS_SUPER_MAGIC = 0xADFF
BEFS_SUPER_MAGIC = 0x42465331
BFS_MAGIC = 0x1BADFACE
CIFS_MAGIC_NUMBER = 0xFF534D42
CODA_SUPER_MAGIC = 0x73757245
COH_SUPER_MAGIC = 0x012FF7B7
CRAMFS_MAGIC = 0x28cd3d45
DEVFS_SUPER_MAGIC = 0x1373
EFS_SUPER_MAGIC = 0x00414A53
EXT_SUPER_MAGIC = 0x137D
EXT2_OLD_SUPER_MAGIC = 0xEF51
EXT2_SUPER_MAGIC = 0xEF53
EXT3_SUPER_MAGIC = 0xEF53
HFS_SUPER_MAGIC = 0x4244
HPFS_SUPER_MAGIC = 0xF995E849
HUGETLBFS_MAGIC = 0x958458f6
ISOFS_SUPER_MAGIC = 0x9660
JFFS2_SUPER_MAGIC = 0x72b6
JFS_SUPER_MAGIC = 0x3153464a
MINIX_SUPER_MAGIC = 0x137F  # orig. minix
MINIX_SUPER_MAGIC2 = 0x138F  # 30 char minix
MINIX2_SUPER_MAGIC = 0x2468  # minix V2
MINIX2_SUPER_MAGIC2 = 0x2478  # minix V2, 30 char names
MSDOS_SUPER_MAGIC = 0x4d44
NCP_SUPER_MAGIC = 0x564c
NFS_SUPER_MAGIC = 0x6969
NTFS_SB_MAGIC = 0x5346544e
OPENPROM_SUPER_MAGIC = 0x9fa1
PROC_SUPER_MAGIC = 0x9fa0
QNX4_SUPER_MAGIC = 0x002f
REISERFS_SUPER_MAGIC = 0x52654973
ROMFS_MAGIC = 0x7275
SMB_SUPER_MAGIC = 0x517B
SYSV2_SUPER_MAGIC = 0x012FF7B6
SYSV4_SUPER_MAGIC = 0x012FF7B5
TMPFS_MAGIC = 0x01021994
UDF_SUPER_MAGIC = 0x15013346
UFS_MAGIC = 0x00011954
USBDEVICE_SUPER_MAGIC = 0x9fa2
VXFS_SUPER_MAGIC = 0xa501FCF5
XENIX_SUPER_MAGIC = 0x012FF7B4
XFS_SUPER_MAGIC = 0x58465342
_XIAFS_SUPER_MAGIC = 0x012FD16D

f_types = {}
for name in dir():
    if name.endswith('MAGIC'):
        hname = name[:-6]
        hname = hname.replace('_SUPER', '')
        f_types[eval(name)] = hname

t1 = time.time()

not_wish_fs_type = set(['sysfs', 'devtmpfs', 'securityfs',
                        'devpts', 'cgroup', 'pstore', 'configfs',
                        'mqueue', 'hugetlbfs', 'autofs', 'fusectl',
                        'proc', 'smbfs', 'cifs', 'iso9660', 'udf',
                        'nfsv4', 'udev'])


def _get_volume_paths():
    fs_paths = []
    with open('/etc/mtab', 'r') as f:
        lines = f.readlines()
        for line in lines:
            line = bytes_to_unicode(line)
            # /dev/md1 / ext4 rw,relatime,errors=remount-ro 0 0
            device, path, fs_type, _ = line.split(' ', 3)
            if fs_type in not_wish_fs_type:
                continue
            
            fs_paths.append((path, fs_type))
    return fs_paths


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
            else:
                print("REMOVING DUPLICATE", path)
    return final_fs_details


def main():
    t2 = time.time()
    r = {}
    fs_path = _get_volume_paths()
    # with open('/etc/mtab', 'r') as f:
    #     lines = f.readlines()
    #     for line in lines:
    #         # /dev/md1 / ext4 rw,relatime,errors=remount-ro 0 0
    #         device, path, fs_type, _ = line.split(' ', 3)
    #         if fs_type in not_wish_fs_type:
    #             continue
    #         print "device", device, "path", path, "fs_type", fs_type
    #         fs_path.append((path, fs_type))
    t3 = time.time()
    import random
    random.shuffle(fs_path)
    
    final_fs_details = _get_and_unduplicate_volume_stats(fs_path)
    # for (path, fs_type) in fs_path:
    #     details = statfs(path)
    #     fs_id = (details.f_fsid[0], details.f_fsid[1])
    #     prev_entry = final_fs_details.get(fs_id, None)
    #     if prev_entry is None:  # new fs
    #         final_fs_details[fs_id] = (path, fs_type, details)
    #     else:
    #         prev_path, _, _ = prev_entry
    #         # is our path shorter than the previous?
    #         if len(path) < len(prev_path):
    #             final_fs_details[fs_id] = (path, fs_type, details)
    #         else:
    #             print "REMOVING DUPLICATE", path
    
    for (path, fs_type, details) in final_fs_details.values():
        print("\n\nPath %s" % path)
        d = {}
        r[path] = d
        print("is on a %s filesystem" % fs_type)  # f_types[details.f_type]
        # print details.__dict__
        # print "f_type:", details.f_type
        
        print("f_bsize:", details.f_bsize)
        print("f_blocks: total data blocks in file system", details.f_blocks)
        print("f_bfree: free blocks in fs", details.f_bfree)
        print("f_bavail:  free blocks avail to non-superuser", details.f_bavail)
        print("f_files:   total file nodes in file system", details.f_files)
        print("f_ffree:   free file nodes in fs", details.f_ffree)
        print("f_fsid:    file system id", details.f_fsid[0], details.f_fsid[1])
        print("f_namelen: maximum length of filenames", details.f_namelen)
        block_size = details.f_bsize
        total_size = int(details.f_blocks * block_size / (1024.0 * 1024.0))
        free_size = int(details.f_bfree * block_size / (1024.0 * 1024.0))
        used_size = total_size - free_size
        pct_used = round(float(100 * float(used_size) / total_size), 0)
        
        print("Total size", total_size, used_size, pct_used, free_size)
        
        d['total'] = total_size
        d['used'] = used_size
        d['pct_used'] = pct_used
    
    t4 = time.time()
    
    print("Times: %.3f  %.3f  %.3f  %.3f" % (t1 - t0, t2 - t1, t3 - t2, t4 - t3))
    print(r)


if __name__ == "__main__":
    main()
