import os
import glob
import imp

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('hosting-context')


# Base class for hosting context. MUST be used
class InterfaceHostingContext(object):
    name = '__MISSING__NAME__'
    is_default = False
    
    class __metaclass__(type):
        __inheritors__ = set()
        
        
        def __new__(meta, name, bases, dct):
            klass = type.__new__(meta, name, bases, dct)
            # When creating the class, we need to look at the module where it is. It will be create like this (in collectormanager)
            # collector___global___windows___collector_iis ==> level=global  pack_name=windows, collector_name=collector_iis
            from_module = dct['__module__']
            elts = from_module.split('___')
            # Note: the master class InterfaceHostingContext will go in this too, but its module won't match the ___ filter
            if len(elts) != 1:
                # Let the klass know it
                klass.pack_level = elts[1]
                klass.pack_name = elts[2]
            
            meta.__inheritors__.add(klass)
            return klass
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    
    def __init__(self):
        self.logger = logger
    
    
    def is_active(self):
        raise NotImplemented()
    
    
    def get_public_address(self):
        raise NotImplemented()


# when you are not a cloud
class OnPremiseHostingContext(InterfaceHostingContext):
    name = 'on-premise'
    is_default = True
    
    
    def __init__(self):
        super(OnPremiseHostingContext, self).__init__()
    
    
    # It's the last one, be active
    def is_active(self):
        return True
    
    
    # TODO: get default system detection
    def get_public_address(self):
        return None


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class HostingContextMgr(object):
    def __init__(self):
        self.context = None
    
    
    def __default_last(self, cls1, cls2):
        if cls1.is_default:
            return 1
        if cls2.is_default:
            return -1
        return 0
    
    
    def detect(self):
        # First get all Hosting context class available
        hostingctx_clss = InterfaceHostingContext.get_sub_class()
        
        hostingctx_clss = sorted(hostingctx_clss, cmp=self.__default_last)
        
        for cls in hostingctx_clss:
            # skip base module Collector
            if cls == InterfaceHostingContext:
                continue
            
            ctx = cls()
            logger.debug('Trying hosting context %s' % ctx.name)
            if ctx.is_active():
                self.context = ctx
                logger.debug('Hosting context is founded: %s' % ctx.name)
                return
    
    
    def load_directory(self, directory, pack_name='', pack_level=''):
        logger.debug('Loading hosting context directory at %s for pack %s' % (directory, pack_name))
        pth = directory + '/hostingcontext_*.py'
        collector_files = glob.glob(pth)
        for f in collector_files:
            fname = os.path.splitext(os.path.basename(f))[0]
            logger.debug('Loading hosting context from file %s' % f)
            try:
                # NOTE: KEEP THE ___ as they are used to let the class INSIDE te module in which pack/level they are. If you have
                # another way to give the information to the inner class inside, I take it ^^
                m = imp.load_source('hostingcontext___%s___%s___%s' % (pack_level, pack_name, fname), f)
                logger.debug('Hosting context module loaded: %s' % m)
            except Exception, exp:
                logger.error('Cannot load hosting context %s: %s' % (fname, exp))
    
    
    def get_public_address(self):
        return self.context.get_public_address()

    
    def is_context_active(self, context_name):
        return self.context.name == context_name
    

    def get_context(self):
        return self.context
    

hostingcontextmgr_ = None


def get_hostingcontextmgr():
    global hostingcontextmgr_
    if hostingcontextmgr_ is None:
        logger.debug('Lazy creation of the hostingcontextmgr class')
        hostingcontextmgr_ = HostingContextMgr()
        # Launch the detection of the context
        hostingcontextmgr_.detect()
    return hostingcontextmgr_
