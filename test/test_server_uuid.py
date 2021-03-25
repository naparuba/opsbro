#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


from opsbro_test import *
from opsbro.util import guess_server_const_uuid


class TestServerUuid(OpsBroTest):
    
    def test_server_uuid(self):
        server_uuid = guess_server_const_uuid()
        self.assertIsNotNone(server_uuid)


if __name__ == '__main__':
    unittest.main()
