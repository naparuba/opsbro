# -*- coding: utf-8 -*-

import sys
import os
import time
from string import digits

from opsbro.collector import Collector
from opsbro.now import NOW

if os.name == 'nt':
    import opsbro.misc.wmi as wmi

BYTES_PER_SECTOR = 512


class IoStats(Collector):
    def __init__(self):
        super(IoStats, self).__init__()
        self.previous_raw = {}
        self.previous_time = 0
        
        # Columns for disk entry in /proc/diskstats
        self.columns_disk = ['major', 'minor', 'device', 'reads', 'reads_merged', 'read_sectors', 'read_ms', 'writes', 'writes_merged', 'write_sectors', 'write_ms', 'cur_ios', 'total_io_ms', 'total_io_weighted_ms']
        # We don't care about theses fields
        # NOTE: write_ms and read_ms are over the sleep time, not sure about what it means
        self.columns_to_del_in_raw = ('major', 'minor', 'cur_ios', 'total_io_weighted_ms', 'read_ms', 'write_ms')
    
    
    def _get_disk_stats(self):
        file_path = '/proc/diskstats'
        result = {}
        
        # ref: http://lxr.osuosl.org/source/Documentation/iostats.txt
        
        # columns_partition = ['major', 'minor', 'device', 'reads', 'rd_sectors', 'writes', 'wr_sectors']
        
        lines = open(file_path, 'r').readlines()
        for line in lines:
            if line == '':
                continue
            split = line.split()
            if len(split) == len(self.columns_disk):
                columns = self.columns_disk
            # elif len(split) == len(columns_partition):
            #    columns = columns_partition
            else:
                # No match, drop partitions too
                continue
            
            data = dict(zip(columns, split))
            
            device_name = data['device']
            
            # If there is a number in the device, we drop (don't look at partition)
            # NOTE: car in digit is faster than regexp re.search('\d+', value)
            # (⌐■_■)==ε╦╤─   regexp
            if any(char in digits for char in device_name):
                continue
            
            for key in data:
                if key != 'device':
                    data[key] = int(data[key])
            # We don't care about some raw fields
            for k in self.columns_to_del_in_raw:
                del data[k]
            
            result[device_name] = data
        
        return result
    
    
    def compute_linux_disk_stats(self, new_raw_stats, diff_time):
        r = {}
        for (device, new_stats) in new_raw_stats.iteritems():
            old_stats = self.previous_raw.get(device, None)
            # A new disk did spawn? wait a loop to compute it
            if old_stats is None:
                continue
            r[device] = {}
            for (k, new_v) in new_stats.iteritems():
                old_v = old_stats[k]
                
                # String= device name, but we already have it in the key path
                if isinstance(old_v, basestring):
                    continue
                # Some columns are finally computed in /s (diff/time)
                elif k in ('reads', 'reads_merged', 'writes', 'writes_merged'):
                    this_type_consumed = int((new_v - old_v) / float(diff_time))
                    r[device][k + '/s'] = this_type_consumed
                # Sectors are transformed into bytes/s
                elif k == 'read_sectors':
                    computed_v = int(BYTES_PER_SECTOR * (new_v - old_v) / float(diff_time))
                    r[device]['read_bytes/s'] = computed_v
                elif k == 'write_sectors':
                    computed_v = int(BYTES_PER_SECTOR * (new_v - old_v) / float(diff_time))
                    r[device]['write_bytes/s'] = computed_v
                # Time are trasnformed into % activity
                # NOTE: ms=> s = *1000
                #       percent= *100
                elif k == 'total_io_ms':
                    computed_v = int(100 * (new_v - old_v) / float(diff_time * 1000))
                    r[device][r'util%'] = computed_v
                else:
                    self.logger.debug('Useless rw stats found: %s' % k)
        return r
    
    
    def launch(self):
        logger = self.logger
        # logger.debug('getIOStats: start')
        
        if os.name == 'nt':
            iostats = {}
            counters = [
                (r'io read /sec', r'\PhysicalDisk(*)\Avg. Disk sec/Read', 100),
                (r'io write /sec', r'\PhysicalDisk(*)\Avg. Disk sec/Write', 100),
            ]
            for c in counters:
                _label = c[0]
                _query = c[1]
                _delay = c[2]
                v = wmi.wmiaccess.get_perf_data(_query, unit='double', delay=_delay)
                iostats[_label] = v
            return iostats
        
        if sys.platform != 'linux2':
            self.set_not_eligible('Unsupported platform for this collector')
            return False
        
        new_stats = self._get_disk_stats()
        new_time = NOW.monotonic()
        # First loop: do a 1s loop an compute it, to directly have results
        if self.previous_time == 0:
            self.previous_time = NOW.monotonic()
            self.previous_raw = new_stats
            time.sleep(1)
            new_stats = self._get_disk_stats()
            new_time = NOW.monotonic()
        
        # NOTE: Thanks to monotonic clock, we cannot get back in time
        
        # So compute the diff
        iostats = self.compute_linux_disk_stats(new_stats, new_time - self.previous_time)
        self.previous_raw = new_stats
        self.previous_time = new_time
        
        return iostats
