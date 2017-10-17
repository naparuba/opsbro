import time

from opsbro.misc.monotonic import monotonic


t0 = monotonic()
print "First monotonic call", monotonic()

time.sleep(3           )

t1 = monotonic()
print "Second", t1
print "Diff", t1 - t0
