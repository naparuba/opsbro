import os
import re
import sys
import socket

from opsbro.collector import Collector
from opsbro.parameters import StringParameter, IntParameter, BoolParameter


class Mysql(Collector):
    parameters = {
        'server'             : StringParameter(default='127.0.0.1'),
        'user'               : StringParameter(default='root'),
        'password'           : StringParameter(default=''),
        'port'               : IntParameter(default=3306),
        'socket'             : StringParameter(default='/var/lib/mysql/mysql.sock'),
        'replication_enabled': BoolParameter(default=False)
    }
    
    
    def __init__(self):
        super(Mysql, self).__init__()
        self.MySQLdb = None
        self.mysqlVersion = None
        self.mysqlConnectionsStore = None
        self.mysqlSlowQueriesStore = None
    
    
    def launch(self):
        
        logger = self.logger
        logger.debug('getMySQLStatus: start')
        
        if not self.is_in_group('mysql'):
            self.set_not_eligible('Please add the mysql group to enable this collector.')
            return
        
        if self.MySQLdb is None:
            # Try import MySQLdb, if installed on the system
            try:
                import MySQLdb
                self.MySQLdb = MySQLdb
            except ImportError, exp1:
                try:
                    mydir = os.path.dirname(__file__)
                    sys.path.insert(0, mydir)
                    import pymysql as MySQLdb
                    self.MySQLdb = MySQLdb
                    sys.path = sys.path[1:]
                except ImportError, exp2:
                    sys.path = sys.path[1:]
                    self.set_error('Unable to import MySQLdb (%s) or embedded pymsql (%s)' % (exp1, exp2))
                    return False
        
        host = self.get_parameter('server')
        user = self.get_parameter('user')
        password = self.get_parameter('password')
        port = self.get_parameter('port')
        mysql_socket = self.get_parameter('socket')
        
        # You can connect with socket or TCP
        if not mysql_socket:
            try:
                db = self.MySQLdb.connect(host=host, user=user, passwd=password, port=port)
            except self.MySQLdb.OperationalError, exp:  # ooooups
                self.set_error('MySQL connection error (server): %s' % exp)
                return False
        elif hasattr(socket, 'AF_UNIX'):
            try:
                db = self.MySQLdb.connect(host='localhost', user=user, passwd=password, port=port, unix_socket=mysql_socket)
            except self.MySQLdb.OperationalError, exp:
                self.set_error('MySQL connection error (socket): %s' % exp)
                return False
        else:
            self.set_error('MySQL is set to connect with unix socket but it is not available for windows.')
            return False
        
        logger.debug('getMySQLStatus: connected')
        
        # Get MySQL version
        if self.mysqlVersion is None:
            logger.debug('getMySQLStatus: mysqlVersion unset storing for first time')
            try:
                cursor = db.cursor()
                cursor.execute('SELECT VERSION()')
                result = cursor.fetchone()
            except self.MySQLdb.OperationalError, message:
                logger.error('getMySQLStatus: MySQL query error when getting version: %s', message)
            
            version = result[0].split('-')  # Might include a description e.g. 4.1.26-log. See http://dev.mysql.com/doc/refman/4.1/en/information-functions.html#function_version
            version = version[0].split('.')
            self.mysqlVersion = []
            
            for string in version:
                number = re.match('([0-9]+)', string)
                number = number.group(0)
                self.mysqlVersion.append(number)
        
        logger.debug('getMySQLStatus: getting Connections')
        
        # Connections
        try:
            cursor = db.cursor()
            cursor.execute('SHOW STATUS LIKE "Connections"')
            result = cursor.fetchone()
        except self.MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Connections = %s', message)
        
        if self.mysqlConnectionsStore is None:
            logger.debug('getMySQLStatus: mysqlConnectionsStore unset storing for first time')
            self.mysqlConnectionsStore = result[1]
            connections = 0
        else:
            logger.debug('getMySQLStatus: mysqlConnectionsStore set so calculating')
            logger.debug('getMySQLStatus: self.mysqlConnectionsStore = %s', self.mysqlConnectionsStore)
            logger.debug('getMySQLStatus: result = %s', result[1])
            connections = float(float(result[1]) - float(self.mysqlConnectionsStore)) / 60
            self.mysqlConnectionsStore = result[1]
        
        logger.debug('getMySQLStatus: connections  = %s', connections)
        logger.debug('getMySQLStatus: getting Connections - done')
        logger.debug('getMySQLStatus: getting Created_tmp_disk_tables')
        
        # Created_tmp_disk_tables
        
        # Determine query depending on version. For 5.02 and above we need the GLOBAL keyword
        if int(self.mysqlVersion[0]) >= 5 and int(self.mysqlVersion[2]) >= 2:
            query = 'SHOW GLOBAL STATUS LIKE "Created_tmp_disk_tables"'
        else:
            query = 'SHOW STATUS LIKE "Created_tmp_disk_tables"'
        
        try:
            cursor = db.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
        except self.MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Created_tmp_disk_tables = %s', message)
        
        createdTmpDiskTables = float(result[1])
        
        logger.debug('getMySQLStatus: createdTmpDiskTables = %s', createdTmpDiskTables)
        logger.debug('getMySQLStatus: getting Created_tmp_disk_tables - done')
        logger.debug('getMySQLStatus: getting Max_used_connections')
        
        # Max_used_connections
        try:
            cursor = db.cursor()
            cursor.execute('SHOW STATUS LIKE "Max_used_connections"')
            result = cursor.fetchone()
        except self.MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Max_used_connections = %s', message)
        
        maxUsedConnections = int(result[1])
        logger.debug('getMySQLStatus: maxUsedConnections = %s', createdTmpDiskTables)
        logger.debug('getMySQLStatus: getting Max_used_connections - done')
        logger.debug('getMySQLStatus: getting Open_files')
        
        # Open_files
        try:
            cursor = db.cursor()
            cursor.execute('SHOW STATUS LIKE "Open_files"')
            result = cursor.fetchone()
        except self.MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Open_files = %s', message)
        
        openFiles = int(result[1])
        
        logger.debug('getMySQLStatus: openFiles = %s', openFiles)
        logger.debug('getMySQLStatus: getting Open_files - done')
        
        # Slow_queries
        logger.debug('getMySQLStatus: getting Slow_queries')
        
        # Determine query depending on version. For 5.02 and above we need the GLOBAL keyword (case 31015)
        if int(self.mysqlVersion[0]) >= 5 and int(self.mysqlVersion[2]) >= 2:
            query = 'SHOW GLOBAL STATUS LIKE "Slow_queries"'
        else:
            query = 'SHOW STATUS LIKE "Slow_queries"'
        try:
            cursor = db.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
        except self.MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Slow_queries = %s', message)
        
        if self.mysqlSlowQueriesStore is None:
            logger.debug('getMySQLStatus: mysqlSlowQueriesStore unset so storing for first time')
            self.mysqlSlowQueriesStore = result[1]
            slowQueries = 0
        
        else:
            logger.debug('getMySQLStatus: mysqlSlowQueriesStore set so calculating')
            logger.debug('getMySQLStatus: self.mysqlSlowQueriesStore = %s', self.mysqlSlowQueriesStore)
            logger.debug('getMySQLStatus: result = %s', result[1])
            
            slowQueries = float(float(result[1]) - float(self.mysqlSlowQueriesStore)) / 60
            
            self.mysqlSlowQueriesStore = result[1]
        
        logger.debug('getMySQLStatus: slowQueries = %s', slowQueries)
        logger.debug('getMySQLStatus: getting Slow_queries - done')
        logger.debug('getMySQLStatus: getting Table_locks_waited')
        
        # Table_locks_waited
        try:
            cursor = db.cursor()
            cursor.execute('SHOW STATUS LIKE "Table_locks_waited"')
            result = cursor.fetchone()
        except self.MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Table_locks_waited = %s', message)
        
        tableLocksWaited = float(result[1])
        
        logger.debug('getMySQLStatus: tableLocksWaited  = %s', tableLocksWaited)
        logger.debug('getMySQLStatus: getting Table_locks_waited - done')
        logger.debug('getMySQLStatus: getting Threads_connected')
        
        # Threads_connected
        try:
            cursor = db.cursor()
            cursor.execute('SHOW STATUS LIKE "Threads_connected"')
            result = cursor.fetchone()
        except self.MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Threads_connected = %s', message)
        
        threadsConnected = int(result[1])
        
        logger.debug('getMySQLStatus: threadsConnected = %s', threadsConnected)
        logger.debug('getMySQLStatus: getting Threads_connected - done')
        logger.debug('getMySQLStatus: getting Seconds_Behind_Master')
        secondsBehindMaster = 0
        if self.get_parameter('replication_enabled'):
            # Seconds_Behind_Master
            try:
                cursor = db.cursor(self.MySQLdb.cursors.DictCursor)
                cursor.execute('SHOW SLAVE STATUS')
                result = cursor.fetchone()
            except self.MySQLdb.OperationalError, message:
                self.set_error('getMySQLStatus: MySQL query error when getting SHOW SLAVE STATUS = %s' % message)
                result = None
            
            if result != None:
                try:
                    secondsBehindMaster = result['Seconds_Behind_Master']
                    logger.debug('getMySQLStatus: secondsBehindMaster = %s' % secondsBehindMaster)
                except IndexError, exp:
                    secondsBehindMaster = None
                    logger.debug('getMySQLStatus: secondsBehindMaster empty. %s' % exp)
            else:
                secondsBehindMaster = None
                logger.debug('getMySQLStatus: secondsBehindMaster empty. Result = None.')
            
            logger.debug('getMySQLStatus: getting Seconds_Behind_Master - done')
        
        return {'connections'          : connections, 'created_tmp_disk_tables': createdTmpDiskTables,
                'max_used_connections' : maxUsedConnections, 'open_files': openFiles, 'slow_queries': slowQueries,
                'table_locks_waited'   : tableLocksWaited, 'threads_connected': threadsConnected,
                'seconds_behind_master': secondsBehindMaster}
