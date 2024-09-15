import importlib.util
import os

try:
    import opsbro
except ImportError:
    #PY2 version:: imp.load_module('opsbro', *imp.find_module('opsbro', [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]))
    opsbro_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location('opsbro', os.path.join(opsbro_path, 'opsbro', '__init__.py'))
    opsbro = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(opsbro)