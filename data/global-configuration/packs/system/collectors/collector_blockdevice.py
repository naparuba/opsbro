import os
import sys
import platform
import multiprocessing
import socket
from kunai.log import logger
from kunai.collector import Collector
from kunai.util import get_public_address


class Blockdevice(Collector):
    def launch(self):
        logger.debug('getBlockdevice: start')
        res = {}
        if not os.path.exists('/sys/block/'):
            return res
        names = os.listdir('/sys/block/')
        for blkname in names:
            # Skip useless ones
            if blkname.startswith('dm-') or blkname.startswith('ram') or blkname.startswith('loop'):
                continue
            
            res[blkname] = {}
            # look for vendor, model and size            
            keys = [('vendor', 'device/vendor'), ('model', 'device/model'), ('size', 'size')]
            for (k, s) in keys:
                pth = '/sys/block/%s/%s' % (blkname, s)
                if os.path.exists(pth):
                    f = open(pth, 'r')
                    v = f.read().strip()
                    f.close()
                    res[blkname][k] = v

        logger.debug('getblockdevice: completed, returning')
        return res
