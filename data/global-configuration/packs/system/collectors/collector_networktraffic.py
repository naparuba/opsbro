import sys
import re
import traceback
import time
import os

from opsbro.collector import Collector
from opsbro.now import NOW

if os.name == 'nt':
    import opsbro.misc.wmi as wmi


class NetworkTraffic(Collector):
    def __init__(self):
        super(NetworkTraffic, self).__init__()
        self.networkTrafficStore = {}
        self.last_launch = 0.0
    
    
    def launch(self):
        logger = self.logger
        now = int(NOW.monotonic())
        diff = now - self.last_launch  # note: thanks to monotonic clock, we cannot have a negative diff
        self.last_launch = now
        
        logger.debug('getNetworkTraffic: start')
        if os.name == 'nt':
            data = {}
            counters = [
                (r'network total bytes/sec', r'\Network Interface(*)\Bytes Total/sec', 100),
            ]
            for c in counters:
                _label = c[0]
                _query = c[1]
                _delay = c[2]
                v = wmi.wmiaccess.get_perf_data(_query, unit='double', delay=_delay)
                data[_label] = v
            return data
        
        if sys.platform == 'linux2':
            logger.debug('getNetworkTraffic: linux2')
            
            try:
                logger.debug('getNetworkTraffic: attempting open')
                proc = open('/proc/net/dev', 'r')
                lines = proc.readlines()
                proc.close()
            
            except IOError, e:
                logger.error('getNetworkTraffic: exception = %s', e)
                return False
            
            logger.debug('getNetworkTraffic: open success, parsing')
            
            columnLine = lines[1]
            _, receiveCols, transmitCols = columnLine.split('|')
            receiveCols = map(lambda a: 'recv_' + a, receiveCols.split())
            transmitCols = map(lambda a: 'trans_' + a, transmitCols.split())
            
            cols = receiveCols + transmitCols
            
            logger.debug('getNetworkTraffic: parsing, looping')
            
            faces = {}
            for line in lines[2:]:
                if line.find(':') < 0:
                    continue
                face, data = line.split(':')
                # skipping lo because we just don't care about it :)
                if face.strip() == 'lo':
                    continue
                faceData = dict(zip(cols, data.split()))
                faces[face] = faceData
            
            logger.debug('getNetworkTraffic: parsed, looping')
            
            interfaces = {}
            
            # Now loop through each interface
            for face in faces:
                key = face.strip()
                
                # We need to work out the traffic since the last check so first time we store the current value
                # then the next time we can calculate the difference
                try:
                    list_of_keys = faces[face].keys()
                    by_sec_keys = ['recv_bytes', 'trans_bytes', 'recv_packets', 'trans_packets']
                    if key in self.networkTrafficStore:
                        interfaces[key] = {}
                        for k in list_of_keys:
                            interfaces[key][k] = long(faces[face][k]) - long(self.networkTrafficStore[key][k])
                            
                            if interfaces[key][k] < 0:
                                interfaces[key][k] = long(faces[face][k])
                            
                            # Only 'recv_bytes', 'trans_bytes' need /s metrics
                            if k in by_sec_keys:
                                interfaces[key]['%s/s' % k] = interfaces[key][k] / diff
                            
                            interfaces[key][k] = long(interfaces[key][k])
                            self.networkTrafficStore[key][k] = long(faces[face][k])
                    
                    else:
                        self.networkTrafficStore[key] = {}
                        for k in list_of_keys:
                            self.networkTrafficStore[key][k] = long(faces[face][k])
                            
                            # Logging
                    logger.debug('getNetworkTraffic: %s = %s' % (key, self.networkTrafficStore[key]['recv_bytes']))
                    logger.debug('getNetworkTraffic: %s = %s' % (key, self.networkTrafficStore[key]['trans_bytes']))
                
                except KeyError, ex:
                    logger.error('getNetworkTraffic: no data for %s' % key)
                except ValueError, ex:
                    logger.error('getNetworkTraffic: invalid data for %s' % key)
            
            logger.debug('getNetworkTraffic: completed, returning')
            return interfaces
        
        elif sys.platform.find('freebsd') != -1:
            logger.debug('getNetworkTraffic: freebsd')
            
            try:
                try:
                    logger.debug('getNetworkTraffic: attempting Popen (netstat)')
                    
                    proc = subprocess.Popen(['netstat', '-nbid'], stdout=subprocess.PIPE, close_fds=True)
                    netstat = proc.communicate()[0]
                    
                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            logger.debug('Process already terminated')
                
                except Exception, e:
                    logger.error('getNetworkTraffic: exception = %s', traceback.format_exc())
                    
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        logger.debug('Process already terminated')
            
            logger.debug('getNetworkTraffic: open success, parsing')
            
            lines = netstat.split('\n')
            
            # Loop over available data for each inteface
            faces = {}
            rxKey = None
            txKey = None
            
            for line in lines:
                logger.debug('getNetworkTraffic: %s', line)
                
                line = re.split(r'\s+', line)
                
                # Figure out which index we need
                if rxKey == None and txKey == None:
                    for k, part in enumerate(line):
                        logger.debug('getNetworkTraffic: looping parts (%s)', part)
                        
                        if part == 'Ibytes':
                            rxKey = k
                            logger.debug('getNetworkTraffic: found rxKey = %s', k)
                        elif part == 'Obytes':
                            txKey = k
                            logger.debug('getNetworkTraffic: found txKey = %s', k)
                
                else:
                    if line[0] not in faces:
                        try:
                            logger.debug('getNetworkTraffic: parsing (rx: %s = %s / tx: %s = %s)', rxKey, line[rxKey],
                                         txKey, line[txKey])
                            faceData = {'recv_bytes': line[rxKey], 'trans_bytes': line[txKey]}
                            
                            face = line[0]
                            faces[face] = faceData
                        except IndexError, e:
                            continue
            
            logger.debug('getNetworkTraffic: parsed, looping')
            
            interfaces = {}
            
            # Now loop through each interface
            for face in faces:
                key = face.strip()
                
                try:
                    # We need to work out the traffic since the last check so first time we store the current value
                    # then the next time we can calculate the difference
                    if key in self.networkTrafficStore:
                        interfaces[key] = {}
                        interfaces[key]['recv_bytes'] = long(faces[face]['recv_bytes']) - long(
                            self.networkTrafficStore[key]['recv_bytes'])
                        interfaces[key]['trans_bytes'] = long(faces[face]['trans_bytes']) - long(
                            self.networkTrafficStore[key]['trans_bytes'])
                        
                        interfaces[key]['recv_bytes'] = str(interfaces[key]['recv_bytes'])
                        interfaces[key]['trans_bytes'] = str(interfaces[key]['trans_bytes'])
                        
                        if interfaces[key]['recv_bytes'] < 0:
                            interfaces[key]['recv_bytes'] = long(faces[face]['recv_bytes'])
                        
                        if interfaces[key]['trans_bytes'] < 0:
                            interfaces[key]['trans_bytes'] = long(faces[face]['trans_bytes'])
                        
                        # And update the stored value to subtract next time round
                        self.networkTrafficStore[key]['recv_bytes'] = faces[face]['recv_bytes']
                        self.networkTrafficStore[key]['trans_bytes'] = faces[face]['trans_bytes']
                    
                    else:
                        self.networkTrafficStore[key] = {}
                        self.networkTrafficStore[key]['recv_bytes'] = faces[face]['recv_bytes']
                        self.networkTrafficStore[key]['trans_bytes'] = faces[face]['trans_bytes']
                
                except KeyError, ex:
                    logger.error('getNetworkTraffic: no data for %s', key)
                
                except ValueError, ex:
                    logger.error('getNetworkTraffic: invalid data for %s', key)
            
            logger.debug('getNetworkTraffic: completed, returning')
            
            return interfaces
        
        else:
            self.set_not_eligible('This system is not managed by this collector.')
            return False
