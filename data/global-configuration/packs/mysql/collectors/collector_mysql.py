import re

from kunai.collector import Collector


class Mysql(Collector):
    def launch(self):
        logger = self.logger
        logger.debug('getMySQLStatus: start')
        
        # Try import MySQLdb - http://sourceforge.net/projects/mysql-python/files/
        try:
            import MySQLdb
        except ImportError, e:
            logger.warning('Unable to import MySQLdb')
            return False
        
        host = self.config.get('mysql_server', 'localhost')
        user = self.config.get('mysql_user', 'root')
        password = self.config.get('mysql_password', 'root')
        port = self.config.get('mysql_port', 3306)
        mysql_socket = self.config.get('mysql_socket', '')
        
        # You can connect with socket or TCP
        if not mysql_socket:
            try:
                db = MySQLdb.connect(host=host, user=user, passwd=password, port=port)
            except MySQLdb.OperationalError, exp:  # ooooups
                self.error('MySQL connection error (server): %s' % exp)
                return False
        else:
            try:
                db = MySQLdb.connect(host='localhost', user=user, passwd=password, port=port, unix_socket=mysql_socket)
            except MySQLdb.OperationalError, exp:
                self.error('MySQL connection error (socket): %s' % exp)
                return False
        
        logger.debug('getMySQLStatus: connected')
        
        # Get MySQL version
        if self.mysqlVersion is None:
            logger.debug('getMySQLStatus: mysqlVersion unset storing for first time')
            try:
                cursor = db.cursor()
                cursor.execute('SELECT VERSION()')
                result = cursor.fetchone()
            except MySQLdb.OperationalError, message:
                logger.error('getMySQLStatus: MySQL query error when getting version: %s', message)
            
            version = result[0].split(
                '-')  # Might include a description e.g. 4.1.26-log. See http://dev.mysql.com/doc/refman/4.1/en/information-functions.html#function_version
            version = version[0].split('.')
            self.mysqlVersion = []
            
            # Make sure the version is only an int. Case 31647
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
        
        except MySQLdb.OperationalError, message:
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
        except MySQLdb.OperationalError, message:
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
        except MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Max_used_connections = %s', message)
        
        maxUsedConnections = result[1]
        logger.debug('getMySQLStatus: maxUsedConnections = %s', createdTmpDiskTables)
        logger.debug('getMySQLStatus: getting Max_used_connections - done')
        logger.debug('getMySQLStatus: getting Open_files')
        
        # Open_files
        try:
            cursor = db.cursor()
            cursor.execute('SHOW STATUS LIKE "Open_files"')
            result = cursor.fetchone()
        except MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Open_files = %s', message)
        
        openFiles = result[1]
        
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
        except MySQLdb.OperationalError, message:
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
        except MySQLdb.OperationalError, message:
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
        except MySQLdb.OperationalError, message:
            logger.error('getMySQLStatus: MySQL query error when getting Threads_connected = %s', message)
        
        threadsConnected = result[1]
        
        logger.debug('getMySQLStatus: threadsConnected = %s', threadsConnected)
        logger.debug('getMySQLStatus: getting Threads_connected - done')
        logger.debug('getMySQLStatus: getting Seconds_Behind_Master')
        
        if 'mysql_norepl' not in self.config:
            # Seconds_Behind_Master
            try:
                cursor = db.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute('SHOW SLAVE STATUS')
                result = cursor.fetchone()
            except MySQLdb.OperationalError, message:
                self.error('getMySQLStatus: MySQL query error when getting SHOW SLAVE STATUS = %s', message)
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
        
        return {'connections'        : connections, 'createdTmpDiskTables': createdTmpDiskTables,
                'maxUsedConnections' : maxUsedConnections, 'openFiles': openFiles, 'slowQueries': slowQueries,
                'tableLocksWaited'   : tableLocksWaited, 'threadsConnected': threadsConnected,
                'secondsBehindMaster': secondsBehindMaster}
