import sys
import re
import traceback
import os

from opsbro.util import lower_dict
from opsbro.collector import Collector

if os.name == 'nt':
    import opsbro.misc.wmi as wmi


class Memory(Collector):
    def launch(self):
        logger = self.logger
        # logger.debug('getMemoryUsage: start')
        if os.name == 'nt':
            data = {}
            # get physical available memory
            _os = wmi.wmiaccess.get_table_where('Win32_OperatingSystem', {})[0]
            data['Memory Total MBytes'] = total_memory = int(_os.TotalVisibleMemorySize) / 1024
            counters = [
                (r'Memory Available MBytes', r'\Memory\Available MBytes', 0),
                (r'swap Input/sec', r'\Memory\Pages Input/sec', 100),
                (r'swap % usage', r'\Paging File(*)\% Usage', 0),
                (r'swap % usage peak', r'\Paging File(*)\% Usage Peak', 0),
            ]
            for c in counters:
                _label = c[0]
                _query = c[1]
                _delay = c[2]
                v = wmi.wmiaccess.get_perf_data(_query, unit='double', delay=_delay)
                data[_label] = v
            data['Memory Usage %'] = 100 * (total_memory - data['Memory Available MBytes']) / total_memory
            return data
        
        # If Linux like procfs system is present and mounted we use meminfo, else we use "native" mode (vmstat and swapinfo)
        if sys.platform.startswith('linux'):
            # logger.debug('getMemoryUsage: linux2')
            try:
                with open('/proc/meminfo', 'r') as meminfoProc:
                    lines = meminfoProc.readlines()
            except IOError as e:
                logger.error('getMemoryUsage: exception = %s', e)
                return False
            
            # logger.debug('getMemoryUsage: open success, parsing')
            regexp = re.compile(r'([0-9]+)')  # We run this several times so one-time compile now
            
            meminfo = {}
            
            # Loop through and extract the numerical values
            for line in lines:
                values = line.split(':')
                try:
                    # Picks out the key (values[0]) and makes a list with the value as the meminfo value (values[1])
                    # We are only interested in the KB data so regexp that out
                    match = re.search(regexp, values[1])
                    
                    if match is not None:
                        meminfo[str(values[0])] = int(match.group(0))
                except IndexError:
                    break
            
            # logger.debug('getMemoryUsage: parsing, looped')
            
            # put all keys in lower case
            meminfo = lower_dict(meminfo)
            memData = {}
            memData['phys_free'] = 0
            memData['phys_used'] = 0
            memData['cached'] = 0
            memData['swap_free'] = 0
            memData['swap_used'] = 0
            
            # Phys
            try:
                # logger.debug('getMemoryUsage: formatting (phys)')
                
                physTotal = meminfo['memtotal']
                physFree = meminfo['memfree'] + meminfo['buffers'] + meminfo['cached'] + meminfo['sreclaimable']  # also count io cache and system one (slab)
                physUsed = 100 * (physTotal - float(physFree)) / physTotal
                
                # Convert to MB
                meminfo['phys_total'] = physTotal
                meminfo['phys_free'] = physFree
                meminfo['phys_used'] = physUsed
            
            # Stops the agent crashing if one of the meminfo elements isn't set
            except IndexError:
                logger.error('getMemoryUsage: formatting (phys) IndexError - cached, memtotal or memfree not present')
            except KeyError:
                logger.error('getMemoryUsage: formatting (phys) KeyError - cached, memtotal or memfree not present')
            
            logger.debug('getMemoryUsage: formatted (phys)')
            
            # Swap
            try:
                # logger.debug('getMemoryUsage: formatting (swap)')
                swapTotal = meminfo['swaptotal']
                swapFree = meminfo['swapfree']
                if swapTotal == 0:
                    swapUsed = 0
                else:
                    swapUsed = 100 * (swapTotal - float(swapFree)) / swapTotal
                
                meminfo['swap_free'] = swapFree
                meminfo['swap_used'] = swapUsed
            
            # Stops the agent crashing if one of the meminfo elements isn't set
            except IndexError:
                logger.error('getMemoryUsage: formatting (swap) IndexError - SwapTotal or SwapFree not present')
            except KeyError:
                logger.error('getMemoryUsage: formatting (swap) KeyError - SwapTotal or SwapFree not present')
            
            logger.debug('getMemoryUsage: formatted (swap), completed, returning')
            return meminfo
        
        elif sys.platform.find('freebsd') != -1:
            logger.debug('getMemoryUsage: freebsd (native)')
            
            physFree = None
            try:
                try:
                    logger.debug('getMemoryUsage: attempting sysinfo')
                    
                    proc = subprocess.Popen(['sysinfo', '-v', 'mem'], stdout=subprocess.PIPE, close_fds=True)
                    sysinfo = proc.communicate()[0]
                    
                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception as e:
                            logger.debug('Process already terminated')
                    
                    sysinfo = sysinfo.split('\n')
                    regexp = re.compile(r'([0-9]+)')  # We run this several times so one-time compile now
                    
                    for line in sysinfo:
                        parts = line.split(' ')
                        if parts[0] == 'Free':
                            logger.debug('getMemoryUsage: parsing free')
                            for part in parts:
                                match = re.search(regexp, part)
                                if match != None:
                                    physFree = match.group(0)
                                    logger.debug('getMemoryUsage: sysinfo: found free %s', physFree)
                        
                        if parts[0] == 'Active':
                            logger.debug('getMemoryUsage: parsing used')
                            
                            for part in parts:
                                match = re.search(regexp, part)
                                if match != None:
                                    physUsed = match.group(0)
                                    logger.debug('getMemoryUsage: sysinfo: found used %s', physUsed)
                        
                        if parts[0] == 'Cached':
                            logger.debug('getMemoryUsage: parsing cached')
                            for part in parts:
                                match = re.search(regexp, part)
                                if match != None:
                                    cached = match.group(0)
                                    logger.debug('getMemoryUsage: sysinfo: found cached %s', cached)
                
                except OSError as e:
                    logger.debug('getMemoryUsage: sysinfo not available')
                except Exception as e:
                    logger.error('getMemoryUsage: exception = %s', traceback.format_exc())
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception as e:
                        logger.debug('Process already terminated')
            
            if physFree == None:
                logger.info(
                    'getMemoryUsage: sysinfo not installed so falling back on sysctl. sysinfo provides more accurate memory info so is recommended. http://www.freshports.org/sysutils/sysinfo')
                
                try:
                    try:
                        logger.debug('getMemoryUsage: attempting Popen (sysctl)')
                        
                        proc = subprocess.Popen(['sysctl', '-n', 'hw.physmem'], stdout=subprocess.PIPE, close_fds=True)
                        physTotal = proc.communicate()[0]
                        
                        if int(pythonVersion[1]) >= 6:
                            try:
                                proc.kill()
                            except Exception as e:
                                logger.debug('Process already terminated')
                        
                        logger.debug('getMemoryUsage: attempting Popen (vmstat)')
                        proc = subprocess.Popen(['vmstat', '-H'], stdout=subprocess.PIPE, close_fds=True)
                        vmstat = proc.communicate()[0]
                        
                        if int(pythonVersion[1]) >= 6:
                            try:
                                proc.kill()
                            except Exception as e:
                                logger.debug('Process already terminated')
                    
                    except Exception as e:
                        logger.error('getMemoryUsage: exception = %s', traceback.format_exc())
                        
                        return False
                finally:
                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception as e:
                            logger.debug('Process already terminated')
                
                logger.debug('getMemoryUsage: Popen success, parsing')
                
                # First we parse the information about the real memory
                lines = vmstat.split('\n')
                physParts = lines[2].split(' ')
                
                physMem = []
                
                # We need to loop through and capture the numerical values
                # because sometimes there will be strings and spaces
                for k, v in enumerate(physParts):
                    
                    if re.match(r'([0-9]+)', v) != None:
                        physMem.append(v)
                
                physTotal = int(physTotal.strip()) / 1024  # physFree is returned in B, but we need KB so we convert it
                physFree = int(physMem[4])
                physUsed = int(physTotal - physFree)
                
                logger.debug('getMemoryUsage: parsed vmstat')
                
                # Convert everything to MB
                physUsed = int(physUsed) / 1024
                physFree = int(physFree) / 1024
                
                cached = 'NULL'
            
            #
            # Swap memory details
            #
            
            logger.debug('getMemoryUsage: attempting Popen (swapinfo)')
            
            try:
                try:
                    proc = subprocess.Popen(['swapinfo', '-k'], stdout=subprocess.PIPE, close_fds=True)
                    swapinfo = proc.communicate()[0]
                    
                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception as e:
                            logger.debug('Process already terminated')
                
                except Exception as e:
                    logger.error('getMemoryUsage: exception = %s', traceback.format_exc())
                    
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception as e:
                        logger.debug('Process already terminated')
            
            lines = swapinfo.split('\n')
            swapUsed = 0
            swapFree = 0
            
            for index in range(1, len(lines)):
                swapParts = re.findall(r'(\d+)', lines[index])
                
                if swapParts != None:
                    try:
                        swapUsed += int(swapParts[len(swapParts) - 3]) / 1024
                        swapFree += int(swapParts[len(swapParts) - 2]) / 1024
                    except IndexError as e:
                        pass
            
            logger.debug('getMemoryUsage: parsed swapinfo, completed, returning')
            
            return {'physUsed': physUsed, 'physFree': physFree, 'swapUsed': swapUsed, 'swapFree': swapFree,
                    'cached'  : cached}
        
        elif sys.platform == 'darwin':
            logger.debug('getMemoryUsage: darwin')
            
            try:
                try:
                    logger.debug('getMemoryUsage: attempting Popen (top)')
                    
                    proc = subprocess.Popen(['top', '-l 1'], stdout=subprocess.PIPE, close_fds=True)
                    top = proc.communicate()[0]
                    
                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception as e:
                            logger.debug('Process already terminated')
                    
                    logger.debug('getMemoryUsage: attempting Popen (sysctl)')
                    proc = subprocess.Popen(['sysctl', 'vm.swapusage'], stdout=subprocess.PIPE, close_fds=True)
                    sysctl = proc.communicate()[0]
                    
                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception as e:
                            logger.debug('Process already terminated')
                
                except Exception as e:
                    logger.error('getMemoryUsage: exception = %s', traceback.format_exc())
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception as e:
                        logger.debug('Process already terminated')
            
            logger.debug('getMemoryUsage: Popen success, parsing')
            
            # Deal with top
            lines = top.split('\n')
            physParts = re.findall(r'([0-9]\d+)', lines[self.topIndex])
            
            logger.debug('getMemoryUsage: parsed top')
            
            # Deal with sysctl
            swapParts = re.findall(r'([0-9]+\.\d+)', sysctl)
            
            logger.debug('getMemoryUsage: parsed sysctl, completed, returning')
            
            return {'physUsed': physParts[3], 'physFree': physParts[4], 'swapUsed': swapParts[1],
                    'swapFree': swapParts[2], 'cached': 'NULL'}
        
        else:
            self.set_not_eligible('This system is not managed by this collector.')
            return False
