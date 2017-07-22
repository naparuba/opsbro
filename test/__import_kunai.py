try:
    import kunai
except ImportError:
    import imp, os
    imp.load_module('kunai',
                    *imp.find_module('kunai',
                                     [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]))

