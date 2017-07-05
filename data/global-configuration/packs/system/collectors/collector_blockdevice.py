import os

from kunai.collector import Collector


class Blockdevice(Collector):
    def launch(self):
        self.logger.debug('getBlockdevice: start')
        res = {}
        if not os.path.exists('/sys/block/'):
            return res
        names = os.listdir('/sys/block/')
        # We will need to remove 0 size block device
        to_del = []
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
                    if k == 'size':
                        v = int(v)
                        # Don't care about purely virtual block device
                        if v == 0:
                            to_del.append(blkname)
        # Clean void block device
        for blkname in to_del:
            del res[blkname]
        
        self.logger.debug('getblockdevice: completed, returning')
        return res
