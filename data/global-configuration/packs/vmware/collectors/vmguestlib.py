### This program is free software; you can redistribute it and/or
### modify it under the terms of the GNU General Public License
### as published by the Free Software Foundation; either version 2
### of the License, or (at your option) any later version.
###
### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.
###
### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

### Copyright 2013-2014 Dag Wieers <dag@wieers.com>

from ctypes import *
from ctypes.util import find_library

__author__ = 'Dag Wieers <dag@wieers.com>'
__version__ = '0.1.2'
__version_info__ = tuple([int(d) for d in __version__.split('.')])
__license__ = 'GNU General Public License (GPL)'

# TODO: Implement support for Windows and MacOSX, improve Linux support ?
if find_library('vmGuestLib'):
    vmGuestLib = CDLL(find_library('vmGuestLib'))
elif find_library('guestlib'):
    vmGuestLib = CDLL(find_library('guestlib'))
# elif os.path.exists('/usr/lib/vmware-tools/lib/libvmGuestLib.so/libvmGuestLib.so'):
#    vmGuestLib = CDLL('/usr/lib/vmware-tools/lib/libvmGuestLib.so/libvmGuestLib.so')
# elif os.path.exists('%PROGRAMFILES%\\VMware\\VMware Tools\\Guest SDK\\vmStatsProvider\win32\\vmGuestLib.dll'):
#    vmGuestLib = CDLL('%PROGRAMFILES%\\VMware\\VMware Tools\\Guest SDK\\vmStatsProvider\win32\\vmGuestLib.dll')
else:
    raise Exception, 'ERROR: Cannot find vmGuestLib library in LD_LIBRARY_PATH'

VMGUESTLIB_ERROR_SUCCESS = 0
VMGUESTLIB_ERROR_OTHER = 1
VMGUESTLIB_ERROR_NOT_RUNNING_IN_VM = 2
VMGUESTLIB_ERROR_NOT_ENABLED = 3
VMGUESTLIB_ERROR_NOT_AVAILABLE = 4
VMGUESTLIB_ERROR_NO_INFO = 5
VMGUESTLIB_ERROR_MEMORY = 6
VMGUESTLIB_ERROR_BUFFER_TOO_SMALL = 7
VMGUESTLIB_ERROR_INVALID_HANDLE = 8
VMGUESTLIB_ERROR_INVALID_ARG = 9
VMGUESTLIB_ERROR_UNSUPPORTED_VERSION = 10

VMErrors = (
    'VMGUESTLIB_ERROR_SUCCESS',
    'VMGUESTLIB_ERROR_OTHER',
    'VMGUESTLIB_ERROR_NOT_RUNNING_IN_VM',
    'VMGUESTLIB_ERROR_NOT_ENABLED',
    'VMGUESTLIB_ERROR_NOT_AVAILABLE',
    'VMGUESTLIB_ERROR_NO_INFO',
    'VMGUESTLIB_ERROR_MEMORY',
    'VMGUESTLIB_ERROR_BUFFER_TOO_SMALL',
    'VMGUESTLIB_ERROR_INVALID_HANDLE',
    'VMGUESTLIB_ERROR_INVALID_ARG',
    'VMGUESTLIB_ERROR_UNSUPPORTED_VERSION',
)

VMErrMsgs = (
    'The function has completed successfully.',
    'An error has occurred. No additional information about the type of error is available.',
    'The program making this call is not running on a VMware virtual machine.',
    'The vSphere Guest API is not enabled on this host, so these functions cannot be used. For information about how to enable the library, see "Context Functions" on page 9.',
    'The information requested is not available on this host.',
    'The handle data structure does not contain any information. You must call VMGuestLib_UpdateInfo to update the data structure.',
    'There is not enough memory available to complete the call.',
    'The buffer is too small to accommodate the function call. For example, when you call VMGuestLib_GetResourcePoolPath, if the path buffer is too small for the resulting resource pool path, the function returns this error. To resolve this error, allocate a larger buffer.',
    'The handle that you used is invalid. Make sure that you have the correct handle and that it is open. It might be necessary to create a new handle using VMGuestLib_OpenHandle.',
    'One or more of the arguments passed to the function were invalid.',
    'The host does not support the requested statistic.',
)


class VMGuestLibException(Exception):
    '''Status code that indicates success orfailure. Each function returns a
       VMGuestLibError code. For information about specific error codes, see "vSphere
       Guest API Error Codes" on page 15. VMGuestLibError is an enumerated type
       defined in vmGuestLib.h.'''
    
    
    def __init__(self, errno):
        self.errno = errno
        self.GetErrorText = vmGuestLib.VMGuestLib_GetErrorText
        self.GetErrorText.restype = c_char_p
        self.message = self.GetErrorText(self.errno)
        self.strerr = VMErrMsgs[self.errno]
    
    
    def __str__(self):
        return '%s\n%s' % (self.message, self.strerr)


class VMGuestLib(Structure):
    def __init__(self):
        # Reference to virtualmachinedata. VMGuestLibHandle is defined in vmGuestLib.h.
        self.handle = self.OpenHandle()
        
        self.UpdateInfo()
        
        # Unique identifier for a session. The session ID changes after a virtual machine is
        # migrated using VMotion, suspended and resumed, or reverted to a snapshot. Any of
        # these events is likely to render any information retrieved with this API invalid. You
        # can use the session ID to detect those events and react accordingly. For example, you
        # can refresh and reset any state that relies on the validity of previously retrieved
        # information.
        
        # Use VMGuestLib_GetSessionId to obtain a valid session ID. A session ID is
        # opaque. You cannot compare a virtual machine session ID with the session IDs from
        # any other virtual machines. You must always call VMGuestLib_GetSessionId after
        # calling VMGuestLib_UpdateInfo.
        
        # VMSessionID is defined in vmSessionId.h
        self.sid = self.GetSessionId()
    
    
    def OpenHandle(self):
        '''Gets a handle for use with other vSphere Guest API functions. The guest library
           handle provides a context for accessing information about the virtual machine.

           Virtual machine statistics and state data are associated with a particular guest library
           handle, so using one handle does not affect the data associated with another handle.'''
        if hasattr(self, 'handle'):
            return self.handle
        else:
            handle = c_void_p()
            ret = vmGuestLib.VMGuestLib_OpenHandle(byref(handle))
            if ret != VMGUESTLIB_ERROR_SUCCESS:
                raise VMGuestLibException(ret)
            return handle
    
    
    def CloseHandle(self):
        '''Releases a handle acquired with VMGuestLib_OpenHandle'''
        if hasattr(self, 'handle'):
            ret = vmGuestLib.VMGuestLib_CloseHandle(self.handle.value)
            if ret != VMGUESTLIB_ERROR_SUCCESS:
                raise VMGuestLibException(ret)
            del (self.handle)
    
    
    def UpdateInfo(self):
        '''Updates information about the virtual machine. This information is associated with
           the VMGuestLibHandle.

           VMGuestLib_UpdateInfo requires similar CPU resources to a system call and
           therefore can affect performance. If you are concerned about performance, minimize
           the number of calls to VMGuestLib_UpdateInfo.

           If your program uses multiple threads, each thread must use a different handle.
           Otherwise, you must implement a locking scheme around update calls. The vSphere
           Guest API does not implement internal locking around access with a handle.'''
        ret = vmGuestLib.VMGuestLib_UpdateInfo(self.handle.value)
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
    
    
    def GetSessionId(self):
        '''Retrieves the VMSessionID for the current session. Call this function after calling
           VMGuestLib_UpdateInfo. If VMGuestLib_UpdateInfo has never been called,
           VMGuestLib_GetSessionId returns VMGUESTLIB_ERROR_NO_INFO.'''
        sid = c_void_p()
        ret = vmGuestLib.VMGuestLib_GetSessionId(self.handle.value, byref(sid))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return sid
    
    
    def GetCpuLimitMHz(self):
        '''Retrieves the upperlimit of processor use in MHz available to the virtual
           machine. For information about setting the CPU limit, see "Limits and
           Reservations" on page 14.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetCpuLimitMHz(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetCpuReservationMHz(self):
        '''Retrieves the minimum processing power in MHz reserved for the virtual
           machine. For information about setting a CPU reservation, see "Limits and
           Reservations" on page 14.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetCpuReservationMHz(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetCpuShares(self):
        '''Retrieves the number of CPU shares allocated to the virtual machine. For
           information about how an ESX server uses CPU shares to manage virtual
           machine priority, see the vSphere Resource Management Guide.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetCpuShares(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetCpuStolenMs(self):
        '''Retrieves the number of milliseconds that the virtual machine was in a
           ready state (able to transition to a run state), but was not scheduled to run.'''
        counter = c_uint64()
        ret = vmGuestLib.VMGuestLib_GetCpuStolenMs(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetCpuUsedMs(self):
        '''Retrieves the number of milliseconds during which the virtual machine
           has used the CPU. This value includes the time used by the guest
           operating system and the time used by virtualization code for tasks for this
           virtual machine. You can combine this value with the elapsed time
           (VMGuestLib_GetElapsedMs) to estimate the effective virtual machine
           CPU speed. This value is a subset of elapsedMs.'''
        counter = c_uint64()
        ret = vmGuestLib.VMGuestLib_GetCpuUsedMs(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetElapsedMs(self):
        '''Retrieves the number of milliseconds that have passed in the virtual
           machine since it last started running on the server. The count of elapsed
           time restarts each time the virtual machine is powered on, resumed, or
           migrated using VMotion. This value counts milliseconds, regardless of
           whether the virtual machine is using processing power during that time.

           You can combine this value with the CPU time used by the virtual machine
           (VMGuestLib_GetCpuUsedMs) to estimate the effective virtual machine
           CPU speed. cpuUsedMs is a subset of this value.'''
        counter = c_uint64()
        ret = vmGuestLib.VMGuestLib_GetElapsedMs(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostCpuUsedMs(self):
        '''Undocumented.'''
        counter = c_uint64()
        ret = vmGuestLib.VMGuestLib_GetHostCpuUsedMs(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemKernOvhdMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemKernOvhdMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemMappedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemMappedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemPhysFreeMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemPhysFreeMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemPhysMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemPhysMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemSharedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemSharedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemSwappedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemSwappedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemUnmappedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemUnmappedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostMemUsedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostMemUsedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetHostNumCpuCores(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostNumCpuCores(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetHostProcessorSpeed(self):
        '''Retrieves the speed of the ESX system's physical CPU in MHz.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetHostProcessorSpeed(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemActiveMB(self):
        '''Retrieves the amount of memory the virtual machine is actively using its
           estimated working set size.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemActiveMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemBalloonedMB(self):
        '''Retrieves the amount of memory that has been reclaimed from this virtual
           machine by the vSphere memory balloon driver (also referred to as the
           "vmmemctl" driver).'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemBalloonedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetMemBalloonMaxMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemBalloonMaxMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetMemBalloonTargetMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemBalloonTargetMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemLimitMB(self):
        '''Retrieves the upper limit of memory that is available to the virtual
           machine. For information about setting a memory limit, see "Limits and
           Reservations" on page 14.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemLimitMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetMemLLSwappedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemLLSwappedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemMappedMB(self):
        '''Retrieves the amount of memory that is allocated to the virtual machine.
           Memory that is ballooned, swapped, or has never been accessed is
           excluded.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemMappedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemOverheadMB(self):
        '''Retrieves the amount of "overhead" memory associated with this virtual
           machine that is currently consumed on the host system. Overhead
           memory is additional memory that is reserved for data structures required
           by the virtualization layer.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemOverheadMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemReservationMB(self):
        '''Retrieves the minimum amount of memory that is reserved for the virtual
           machine. For information about setting a memory reservation, see "Limits
           and Reservations" on page 14.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemReservationMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemSharedMB(self):
        '''Retrieves the amount of physical memory associated with this virtual
           machine that is copy-on-write (COW) shared on the host.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemSharedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemSharedSavedMB(self):
        '''Retrieves the estimated amount of physical memory on the host saved
           from copy-on-write (COW) shared guest physical memory.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemSharedSavedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemShares(self):
        '''Retrieves the number of memory shares allocated to the virtual machine.
           For information about how an ESX server uses memory shares to manage
           virtual machine priority, see the vSphere Resource Management Guide.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemShares(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemSwappedMB(self):
        '''Retrieves the amount of memory that has been reclaimed from this virtual
           machine by transparently swapping guest memory to disk.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemSwappedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetMemSwapTargetMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemSwapTargetMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemTargetSizeMB(self):
        '''Retrieves the size of the target memory allocation for this virtual machine.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemTargetSizeMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    def GetMemUsedMB(self):
        '''Retrieves the estimated amount of physical host memory currently
           consumed for this virtual machine's physical memory.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemUsedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetMemZippedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemZippedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
    
    
    # TODO: Undocumented routine, needs testing
    def GetMemZipSavedMB(self):
        '''Undocumented.'''
        counter = c_uint()
        ret = vmGuestLib.VMGuestLib_GetMemZipSavedMB(self.handle.value, byref(counter))
        if ret != VMGUESTLIB_ERROR_SUCCESS:
            raise VMGuestLibException(ret)
        return counter.value
        
        # vim:ts=4:sw=4:et
