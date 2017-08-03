import os
import sys
import re
import traceback

from opsbro.collector import Collector

if os.name == 'nt':
    import opsbro.misc.wmi as wmi


class CpuStats(Collector):
    def launch(self):
        logger = self.logger
        logger.debug('getCPUStats: start')
        
        cpuStats = {}
        
        if os.name == 'nt':
            counters = [
                (r'cpu usage %', r'\Processor(_Total)\% Processor Time', 100),
                (r'cpu_kernel_%', r'\Processor(_Total)\% Privileged Time', 100),
                (r'cpu_user_%', r'\Processor(_Total)\% User Time', 100)
            ]
            for c in counters:
                _label = c[0]
                _query = c[1]
                _delay = c[2]
                v = wmi.wmiaccess.get_perf_data(_query, unit='double', delay=_delay)
                cpuStats[_label] = v
            return cpuStats
        
        if sys.platform == 'linux2':
            logger.debug('getCPUStats: linux2')
            
            headerRegexp = re.compile(r'.*?([%][a-zA-Z0-9]+)[\s+]?')
            itemRegexp = re.compile(r'.*?\s+(\d+)[\s+]?')
            itemRegexpAll = re.compile(r'.*?\s+(all)[\s+]?')
            valueRegexp = re.compile(r'\d+\.\d+')
            
            try:
                cmd = 'mpstat -P ALL 1 1'
                stats = self.execute_shell(cmd)
                if not stats:
                    return None
                stats = stats.split('\n')
                header = stats[2]
                headerNames = re.findall(headerRegexp, header)
                device = None
                
                for statsIndex in range(3, len(stats)):  # no skip "all"
                    row = stats[statsIndex]
                    
                    if not row:  # skip the averages
                        break
                    deviceMatchAll = re.match(itemRegexpAll, row)
                    deviceMatch = re.match(itemRegexp, row)
                    if deviceMatchAll is not None:
                        device = 'cpuall'
                    elif deviceMatch is not None:
                        device = 'cpu%s' % deviceMatch.groups()[0]
                    
                    values = re.findall(valueRegexp, row.replace(',', '.'))
                    
                    cpuStats[device] = {}
                    for headerIndex in range(0, len(headerNames)):
                        headerName = headerNames[headerIndex]
                        cpuStats[device][headerName] = float(values[headerIndex])
            
            except Exception:
                logger.error('getCPUStats: exception = %s', traceback.format_exc())
                return False
        else:
            logger.debug('getCPUStats: unsupported platform')
            return False
        
        logger.debug('getCPUStats: completed, returning')
        return cpuStats
