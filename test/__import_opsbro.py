import imp
import os

try:
    import opsbro
except ImportError:
    imp.load_module('opsbro', *imp.find_module('opsbro', [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]))
