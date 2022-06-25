import traceback
import datetime
import os
import sys

try:  # Python 2
    from urlparse import urlparse
except ImportError:  # python3
    from urllib.parse import urlparse
    
    basestring = str
from numbers import Number

from opsbro.collector import Collector
from opsbro.util import to_best_int_float
from opsbro.parameters import StringParameter, BoolParameter


class Mongodb(Collector):
    parameters = {
        'uri'         : StringParameter(default='mongodb://localhost'),
        'user'        : StringParameter(default=''),
        'password'    : StringParameter(default=''),
        'replicat_set': BoolParameter(default=False),
    }
    
    
    def __init__(self):
        super(Mongodb, self).__init__()
        self.pymongo = None
        self.mongoDBStore = None
    
    
    def _clean_struct(self, e):
        to_del = []
        if isinstance(e, dict):
            for (k, v) in e.items():
                if isinstance(v, dict):
                    self._clean_struct(v)
                    continue
                if isinstance(v, list) or isinstance(v, tuple):
                    for sub_e in v:
                        self._clean_struct(sub_e)
                    continue
                if not isinstance(v, Number) and not isinstance(v, basestring):
                    self.logger.debug('CLEANING bad entry type: %s %s %s' % (k, v, type(v)))
                    to_del.append(k)
                    continue
        for k in to_del:
            del e[k]
    
    
    def launch(self):
        logger = self.logger
        logger.debug('getMongoDBStatus: start')
        
        if not self.is_in_group('mongodb'):
            self.set_not_eligible('Please add the mongodb group to enable this collector.')
            return
        
        # Try to import pymongo from system (will be the best choice)
        # but if no available, switch to the embedded one
        # NOTE: the embedded is a 2.9.2 with centos 7.so file, but in other ditro only the c
        # extension will not load, but it's not a real problem as we don't care about the lib perf here
        if self.pymongo is None:
            try:
                import pymongo
                self.pymongo = pymongo
            except ImportError:
                my_dir = os.path.abspath(os.path.dirname(__file__))
                sys.path.insert(0, my_dir)
                try:
                    import pymongo
                    self.pymongo = pymongo
                except ImportError as exp:
                    self.set_error('Unable to import pymongo library, even the embedded one (%s)' % exp)
                    return False
                finally:
                    try:
                        sys.path.remove(my_dir)
                    except:
                        pass
        
        try:
            mongoURI = ''
            parsed = urlparse(self.get_parameter('uri'))
            
            # Can't use attributes on Python 2.4
            if parsed[0] != 'mongodb':
                mongoURI = 'mongodb://'
                if parsed[2]:
                    if parsed[0]:
                        mongoURI = mongoURI + parsed[0] + ':' + parsed[2]
                    else:
                        mongoURI = mongoURI + parsed[2]
            else:
                mongoURI = self.get_parameter('uri')
            
            logger.debug('-- mongoURI: %s', mongoURI)
            if hasattr(self.pymongo, 'Connection'):  # Old pymongo
                conn = self.pymongo.Connection(mongoURI, slave_okay=True)
            else:  # new pymongo (> 2.9.5)
                conn = self.pymongo.MongoClient(mongoURI)
            logger.debug('Connected to MongoDB')
        except self.pymongo.errors.ConnectionFailure as exp:
            self.set_error('Unable to connect to MongoDB server %s - Exception = %s' % (mongoURI, exp))
            return False
        
        # Older versions of pymongo did not support the command()
        # method below.
        try:
            db = conn['test']  # test is better than local, because local can't be used through mongos
            
            # Server status
            statusOutput = db.command('serverStatus')  # Shorthand for {'serverStatus': 1}
            
            logger.debug('getMongoDBStatus: executed serverStatus')
            
            # Setup            
            status = {'available': True}
            self._clean_struct(statusOutput)  # remove objects type we do not want
            status.update(statusOutput)
            
            # Version
            try:
                status['version'] = statusOutput['version']
                logger.debug('getMongoDBStatus: version %s', statusOutput['version'])
            except KeyError as ex:
                logger.error('getMongoDBStatus: version KeyError exception = %s', ex)
                pass
            
            # Global locks
            try:
                logger.debug('getMongoDBStatus: globalLock')
                
                status['globalLock'] = {}
                status['globalLock']['ratio'] = statusOutput['globalLock']['ratio']
                
                status['globalLock']['currentQueue'] = {}
                status['globalLock']['currentQueue']['total'] = statusOutput['globalLock']['currentQueue']['total']
                status['globalLock']['currentQueue']['readers'] = statusOutput['globalLock']['currentQueue']['readers']
                status['globalLock']['currentQueue']['writers'] = statusOutput['globalLock']['currentQueue']['writers']
            
            except KeyError as ex:
                logger.debug('getMongoDBStatus: globalLock KeyError exception = %s' % ex)
                pass
            
            # Memory
            try:
                logger.debug('getMongoDBStatus: memory')
                
                status['mem'] = {}
                status['mem']['resident'] = statusOutput['mem']['resident']
                status['mem']['virtual'] = statusOutput['mem']['virtual']
                status['mem']['mapped'] = statusOutput['mem']['mapped']
            
            except KeyError as ex:
                logger.debug('getMongoDBStatus: memory KeyError exception = %s', ex)
                pass
            
            # Connections
            try:
                logger.debug('getMongoDBStatus: connections')
                
                status['connections'] = {}
                status['connections']['current'] = statusOutput['connections']['current']
                status['connections']['available'] = statusOutput['connections']['available']
            
            except KeyError as ex:
                logger.debug('getMongoDBStatus: connections KeyError exception = %s', ex)
                pass
            
            # Extra info (Linux only)
            try:
                logger.debug('getMongoDBStatus: extra info')
                
                status['extraInfo'] = {}
                status['extraInfo']['heapUsage'] = statusOutput['extra_info']['heap_usage_bytes']
                status['extraInfo']['pageFaults'] = statusOutput['extra_info']['page_faults']
            
            except KeyError as ex:
                logger.debug('getMongoDBStatus: extra info KeyError exception = %s', ex)
                pass
            
            # Background flushing
            try:
                logger.debug('getMongoDBStatus: backgroundFlushing')
                
                status['backgroundFlushing'] = {}
                delta = datetime.datetime.utcnow() - statusOutput['backgroundFlushing']['last_finished']
                status['backgroundFlushing']['secondsSinceLastFlush'] = delta.seconds
                status['backgroundFlushing']['lastFlushLength'] = statusOutput['backgroundFlushing']['last_ms']
                status['backgroundFlushing']['flushLengthAvrg'] = statusOutput['backgroundFlushing']['average_ms']
            
            except KeyError as ex:
                logger.debug('getMongoDBStatus: backgroundFlushing KeyError exception = %s', ex)
                pass
            
            # Per second metric calculations (opcounts and asserts)
            try:
                if self.mongoDBStore is None:
                    logger.debug('getMongoDBStatus: per second metrics no cached data, so storing for first time')
                    self.setMongoDBStore(statusOutput)
                
                else:
                    logger.debug('getMongoDBStatus: per second metrics cached data exists')
                    
                    accessesPS = float(statusOutput['indexCounters']['btree']['accesses'] -
                                       self.mongoDBStore['indexCounters']['btree']['accessesPS']) / 60
                    
                    if accessesPS >= 0:
                        status['indexCounters'] = {}
                        status['indexCounters']['btree'] = {}
                        status['indexCounters']['btree']['accessesPS'] = accessesPS
                        status['indexCounters']['btree']['hitsPS'] = float(
                            statusOutput['indexCounters']['btree']['hits'] -
                            self.mongoDBStore['indexCounters']['btree']['hitsPS']) / 60
                        status['indexCounters']['btree']['missesPS'] = float(
                            statusOutput['indexCounters']['btree']['misses'] -
                            self.mongoDBStore['indexCounters']['btree']['missesPS']) / 60
                        status['indexCounters']['btree']['missRatioPS'] = float(
                            statusOutput['indexCounters']['btree']['missRatio'] -
                            self.mongoDBStore['indexCounters']['btree']['missRatioPS']) / 60
                        
                        status['opcounters'] = {}
                        status['opcounters']['insertPS'] = float(
                            statusOutput['opcounters']['insert'] - self.mongoDBStore['opcounters']['insertPS']) / 60
                        status['opcounters']['queryPS'] = float(
                            statusOutput['opcounters']['query'] - self.mongoDBStore['opcounters']['queryPS']) / 60
                        status['opcounters']['updatePS'] = float(
                            statusOutput['opcounters']['update'] - self.mongoDBStore['opcounters']['updatePS']) / 60
                        status['opcounters']['deletePS'] = float(
                            statusOutput['opcounters']['delete'] - self.mongoDBStore['opcounters']['deletePS']) / 60
                        status['opcounters']['getmorePS'] = float(
                            statusOutput['opcounters']['getmore'] - self.mongoDBStore['opcounters']['getmorePS']) / 60
                        status['opcounters']['commandPS'] = float(
                            statusOutput['opcounters']['command'] - self.mongoDBStore['opcounters']['commandPS']) / 60
                        
                        status['asserts'] = {}
                        status['asserts']['regularPS'] = float(
                            statusOutput['asserts']['regular'] - self.mongoDBStore['asserts']['regularPS']) / 60
                        status['asserts']['warningPS'] = float(
                            statusOutput['asserts']['warning'] - self.mongoDBStore['asserts']['warningPS']) / 60
                        status['asserts']['msgPS'] = float(
                            statusOutput['asserts']['msg'] - self.mongoDBStore['asserts']['msgPS']) / 60
                        status['asserts']['userPS'] = float(
                            statusOutput['asserts']['user'] - self.mongoDBStore['asserts']['userPS']) / 60
                        status['asserts']['rolloversPS'] = float(
                            statusOutput['asserts']['rollovers'] - self.mongoDBStore['asserts']['rolloversPS']) / 60
                        
                        self.setMongoDBStore(statusOutput)
                    else:
                        logger.debug(
                            'getMongoDBStatus: per second metrics negative value calculated, mongod likely restarted, so clearing cache')
                        self.setMongoDBStore(statusOutput)
            
            except KeyError as ex:
                logger.debug('getMongoDBStatus: per second metrics KeyError exception = %s' % ex)
                pass
            
            # Cursors
            try:
                logger.debug('getMongoDBStatus: cursors')
                
                status['cursors'] = {}
                status['cursors']['totalOpen'] = statusOutput['cursors']['totalOpen']
            
            except KeyError as ex:
                logger.debug('getMongoDBStatus: cursors KeyError exception = %s' % ex)
                pass
            
            # Replica set status
            if self.get_parameter('replicat_set'):
                logger.debug('getMongoDBStatus: get replset status too')
                
                # isMaster (to get state
                isMaster = db.command('isMaster')
                
                logger.debug('getMongoDBStatus: executed isMaster')
                
                status['replSet'] = {}
                status['replSet']['setName'] = isMaster['setName']
                status['replSet']['isMaster'] = isMaster['ismaster']
                status['replSet']['isSecondary'] = isMaster['secondary']
                
                if 'arbiterOnly' in isMaster:
                    status['replSet']['isArbiter'] = isMaster['arbiterOnly']
                
                logger.debug('getMongoDBStatus: finished isMaster')
                
                # rs.status()
                db = conn['admin']
                replSet = db.command('replSetGetStatus')
                
                logger.debug('getMongoDBStatus: executed replSetGetStatus')
                
                status['replSet']['myState'] = replSet['myState']
                status['replSet']['members'] = {}
                
                for member in replSet['members']:
                    
                    logger.debug('getMongoDBStatus: replSetGetStatus looping %s', member['name'])
                    
                    status['replSet']['members'][str(member['_id'])] = {}
                    status['replSet']['members'][str(member['_id'])]['name'] = member['name']
                    status['replSet']['members'][str(member['_id'])]['state'] = member['state']
                    
                    # Optime delta (only available from not self)
                    # Calculation is from http://docs.python.org/library/datetime.html#datetime.timedelta.total_seconds
                    if 'optimeDate' in member:  # Only available as of 1.7.2
                        deltaOptime = datetime.datetime.utcnow() - member['optimeDate']
                        status['replSet']['members'][str(member['_id'])]['optimeDate'] = (deltaOptime.microseconds + (
                                deltaOptime.seconds + deltaOptime.days * 24 * 3600) * 10 ** 6) / 10 ** 6
                    
                    if 'self' in member:
                        status['replSet']['myId'] = member['_id']
                    
                    # Have to do it manually because total_seconds() is only available as of Python 2.7
                    else:
                        if 'lastHeartbeat' in member:
                            deltaHeartbeat = datetime.datetime.utcnow() - member['lastHeartbeat']
                            status['replSet']['members'][str(member['_id'])]['lastHeartbeat'] = (
                                                                                                        deltaHeartbeat.microseconds + (
                                                                                                        deltaHeartbeat.seconds + deltaHeartbeat.days * 24 * 3600) * 10 ** 6) / 10 ** 6
                    
                    if 'errmsg' in member:
                        status['replSet']['members'][str(member['_id'])]['error'] = member['errmsg']
            
            # db.stats()
            logger.debug('getMongoDBStatus: db.stats() too')
            status['dbStats'] = {}
            for database in conn.database_names():
                if database != 'config' and database != 'local' and database != 'admin' and database != 'test':
                    logger.debug('getMongoDBStatus: executing db.stats() for %s', database)
                    status['dbStats'][database] = conn[database].command('dbstats')
                    status['dbStats'][database]['namespaces'] = conn[database]['system']['namespaces'].count()
                    
                    # Ensure all strings to prevent JSON parse errors. We typecast on the server
                    for key in status['dbStats'][database].keys():
                        status['dbStats'][database][key] = str(status['dbStats'][database][key])
                        # try a float/int cast
                        v = to_best_int_float(status['dbStats'][database][key])
                        if v is not None:
                            status['dbStats'][database][key] = v
        
        except Exception:
            logger.error('Unable to get MongoDB status - Exception = %s', traceback.format_exc())
            return False
        
        logger.debug('getMongoDBStatus: completed, returning')
        
        return status
    
    
    def setMongoDBStore(self, statusOutput):
        self.mongoDBStore = {}
        
        self.mongoDBStore['indexCounters'] = {}
        self.mongoDBStore['indexCounters']['btree'] = {}
        self.mongoDBStore['indexCounters']['btree']['accessesPS'] = statusOutput['indexCounters']['btree']['accesses']
        self.mongoDBStore['indexCounters']['btree']['hitsPS'] = statusOutput['indexCounters']['btree']['hits']
        self.mongoDBStore['indexCounters']['btree']['missesPS'] = statusOutput['indexCounters']['btree']['misses']
        self.mongoDBStore['indexCounters']['btree']['missRatioPS'] = statusOutput['indexCounters']['btree']['missRatio']
        
        self.mongoDBStore['opcounters'] = {}
        self.mongoDBStore['opcounters']['insertPS'] = statusOutput['opcounters']['insert']
        self.mongoDBStore['opcounters']['queryPS'] = statusOutput['opcounters']['query']
        self.mongoDBStore['opcounters']['updatePS'] = statusOutput['opcounters']['update']
        self.mongoDBStore['opcounters']['deletePS'] = statusOutput['opcounters']['delete']
        self.mongoDBStore['opcounters']['getmorePS'] = statusOutput['opcounters']['getmore']
        self.mongoDBStore['opcounters']['commandPS'] = statusOutput['opcounters']['command']
        
        self.mongoDBStore['asserts'] = {}
        self.mongoDBStore['asserts']['regularPS'] = statusOutput['asserts']['regular']
        self.mongoDBStore['asserts']['warningPS'] = statusOutput['asserts']['warning']
        self.mongoDBStore['asserts']['msgPS'] = statusOutput['asserts']['msg']
        self.mongoDBStore['asserts']['userPS'] = statusOutput['asserts']['user']
        self.mongoDBStore['asserts']['rolloversPS'] = statusOutput['asserts']['rollovers']
