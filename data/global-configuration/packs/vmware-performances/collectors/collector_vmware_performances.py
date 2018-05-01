import time
import os
import sys
import threading

from opsbro.collector import Collector

# WARNING: the lib initialisation & object handler opening MUST
# be set in the main thread (if in a sub thread, it will segfault)
# Time: load lib ~20ms, create handler=nothing
lib_ptr = None

my_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, my_dir)
try:
    from vmguestlib import VMGuestLib
    
    lib_ptr = VMGuestLib()
except Exception as exp:
    pass
finally:
    try:
        sys.path.remove(my_dir)
    except:
        pass


class VmwarePerformances(Collector):
    def __init__(self):
        super(VmwarePerformances, self).__init__()
        self.prev_stolen_ms = 0
        self.prev_used_ms = 0
        self.prev_elapsed_ms = 0
        self.VMGuestLib = None
        # the vmware lib DON'T manage concurrent access, lock all
        self.lock = threading.RLock()
    
    
    def launch(self):
        with self.lock:
            return self.do_launch()
    
    
    def do_launch(self):
        global lib_ptr
        
        res = {'vmware_tools_available': False, 'cpu': {}, 'memory': {}}
        if lib_ptr is None:
            self.set_not_eligible('The vmware tools are not installed on this server.')
            return res
        
        res['vmware_tools_available'] = True
        lib_ptr.UpdateInfo()
        
        # Then read them
        new_stolen_ms = lib_ptr.GetCpuStolenMs()
        new_used_ms = lib_ptr.GetCpuUsedMs()
        new_elapsed_ms = lib_ptr.GetElapsedMs()
        
        # If first loop, do the
        if self.prev_elapsed_ms == 0:
            # ok so wait for 1s to compute the diff
            self.prev_stolen_ms = new_stolen_ms
            self.prev_used_ms = new_used_ms
            self.prev_elapsed_ms = new_elapsed_ms
            time.sleep(1)
            
            lib_ptr.UpdateInfo()
            new_stolen_ms = lib_ptr.GetCpuStolenMs()
            new_used_ms = lib_ptr.GetCpuUsedMs()
            new_elapsed_ms = lib_ptr.GetElapsedMs()
        
        # Now we are sure new and old, compute the percent
        time_elapsed = new_elapsed_ms - self.prev_elapsed_ms
        used_cpu_pct = 100 * (new_used_ms - self.prev_used_ms) / time_elapsed
        stolen_cpu_pct = 100 * (new_stolen_ms - self.prev_stolen_ms) / time_elapsed
        effective_cpu_mhz = lib_ptr.GetHostProcessorSpeed() * (new_used_ms - self.prev_used_ms) / time_elapsed
        
        self.prev_stolen_ms = new_stolen_ms
        self.prev_used_ms = new_used_ms
        self.prev_elapsed_ms = new_elapsed_ms
        
        res['cpu']['used_cpu_pct'] = used_cpu_pct
        res['cpu']['stolen_cpu_pct'] = stolen_cpu_pct
        res['cpu']['effective_cpu_mhz'] = effective_cpu_mhz
        
        memory = res['memory']
        memory['active'] = lib_ptr.GetMemActiveMB()
        memory['ballooned'] = lib_ptr.GetMemBalloonedMB()
        memory['mapped'] = lib_ptr.GetMemMappedMB()
        memory['overhead'] = lib_ptr.GetMemOverheadMB()
        memory['shared'] = lib_ptr.GetMemSharedMB()
        memory['shared_saved'] = lib_ptr.GetMemSharedSavedMB()
        memory['swapped'] = lib_ptr.GetMemSwappedMB()
        memory['used'] = lib_ptr.GetMemUsedMB()
        
        return res
