try:
    import opsbro
except ImportError:
    import imp, os
    imp.load_module('opsbro',
                    *imp.find_module('opsbro',
                                     [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]))

