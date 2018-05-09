import sys
sys.path.insert(0, '.')
import opsbro
from opsbro.misc.internalleveldb import leveldb as leveldb_ctypes
import leveldb

from opsbro.misc.sqlitedict import SqliteDict


import time

t0 = time.time()
dbc = leveldb_ctypes.DB('/tmp/test', create_if_missing=True)

t1 = time.time()
dbn = leveldb.LevelDB('/tmp/test2')

t2 = time.time()
dbq = SqliteDict('/tmp/sqlite', autocommit=True)
end= time.time()
print "OPEN   Ctypes: %.2f Native: %.2f Sqlite: %.2f" % ((t1 - t0), t2 - t1, end - t2)


N = 10000

t0 = time.time()
for i in xrange(N):
    key = value = '%d' % i
    dbc.put(key, value)
t1 = time.time()

for i in xrange(N):
    key = value = '%d' % i
    dbn.Put(key, value)
t2 = time.time()

for i in xrange(N):
    key = value = '%d' % i
    dbq[key] = value
    
end = time.time()

ctypes_put = t1 - t0
ctypes_put_speed = float(N) / ctypes_put

ntypes_put = t2 - t1
ntypes_put_speed = float(N) / ntypes_put


qtypes_put = end - t2
qtypes_put_speed = float(N) / qtypes_put

print "PUT (%d)    Ctypes: %.2f(%d put/s) Native: %.2f (%d put/s)  Sqlite: %.2f (%d put/s)" % (N, ctypes_put, ctypes_put_speed, ntypes_put, ntypes_put_speed, qtypes_put, qtypes_put_speed)




t0 = time.time()
for i in xrange(N):
    key = value = '%d' % i
    v2 = dbc.get(key)
    assert v2 == value
t1 = time.time()

for i in xrange(N):
    key = value = '%d' % i
    v2 = dbn.Get(key)
    assert v2 == value
t2 = time.time()

for i in xrange(N):
    key = value = '%d' % i
    v2 = dbq[key]
    assert v2 == value
end = time.time()

ctypes_put = t1 - t0
ctypes_put_speed = float(N) / ctypes_put

ntypes_put = t2 - t1
ntypes_put_speed = float(N) / ntypes_put

qtypes_put = end - t2
qtypes_put_speed = float(N) / qtypes_put

print "GET (%d)    Ctypes: %.2f(%d get/s) Native: %.2f (%d get/s)    Sqlite: %.2f (%d get/s)" % (N, ctypes_put, ctypes_put_speed, ntypes_put, ntypes_put_speed, qtypes_put, qtypes_put_speed )




t0 = time.time()
dbc.close()

t1 = time.time()
del dbn

print "Close   Ctypes: %.2f Native: %.2f" % ((t1 - t0), time.time() - t1)



#OPEN   Ctypes: 0.02 Native: 0.03 Sqlite: 0.00
#PUT (10000)    Ctypes: 0.22(45825 put/s) Native: 0.06 (155257 put/s)  Sqlite: 0.73 (13729 put/s)
#GET (10000)    Ctypes: 0.37(26946 get/s) Native: 0.05 (214901 get/s)    Sqlite: 3.24 (3083 get/s)

# Native =  5*ctypes = 100 * sqlite
