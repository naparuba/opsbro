
# -*- coding: utf-8 -*-
import sys


sys.path.insert(0, '.')

uri = 'https://binaries.cockroachdb.com/cockroach-v2.0.0.linux-amd64.tgz'
from opsbro.httpclient import get_http_exceptions, httper
r = httper.get(uri)
print('Result: r')
