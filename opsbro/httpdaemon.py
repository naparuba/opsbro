import json
from opsbro.misc.bottle import run, request, abort, error, redirect, response, gserver
from opsbro.misc.bottle import route as bottle_route
import opsbro.misc.bottle as bottle

bottle.debug(True)

from opsbro.log import logger

exported_functions = {}


# propose a decorator to export http function, and so provide way to
# list them, propose automatic handling (protection or json dump, etc)
def http_export(_route, method='GET', protected=False):
    def decorator(f):
        # Maybe it was already exported, just stack the route and exit
        if f not in exported_functions:
            exported_functions[f] = {'routes': [], 'method': method}
        exported_functions[f]['routes'].append(_route)
        logger.debug('Exporting a function %s as a HTTP route %s and method %s' % (f, _route, method))
        bottle_route(_route, callback=f, method=[method, 'OPTIONS'])
        # and protect it from external queries
        if protected:
            f.protected = True
        return f
    
    
    return decorator


# We want the http daemon to be accessible from everywhere without issue
class EnableCors(object):
    name = 'enable_cors'
    api = 2
    
    
    def apply(self, fn, context):
        def _enable_cors(*args, **kwargs):
            # Set CORS headers
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS, DELETE, PATCH'
            response.headers[
                'Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, X-Shinken-Token'
            response.headers['Access-Control-Allow-Crendentials'] = 'true'
            if bottle.request.method != 'OPTIONS':
                # actual request; reply with the actual response
                return fn(*args, **kwargs)
        
        
        return _enable_cors


# Some calls should be directly available directly in
# the internal webserver (unix one)
class ExternalHttpProtectionLookup(object):
    name = 'externalhttp_protection'
    api = 2
    
    
    def apply(self, fn, context):
        def _externalhttp_protection(*args, **kwargs):
            # if it's a protected function, look if it's
            # an internal call (ok) or not :)
            if getattr(fn, 'protected', False):
                # SERVER PORT will be something like 6768 in external port
                # and '' in the internal one. Cannot be spooffed ^^
                SERVER_PORT = bottle.request.environ['SERVER_PORT']
                internal_server = (SERVER_PORT == '')
                if not internal_server:
                    return bottle.abort(401)
            
            # actual request; reply with the actual response
            return fn(*args, **kwargs)
        
        
        return _externalhttp_protection


# This class is the http daemon main interface
# in a singleton mode so you can easily register new uri from other
# part of the code, mainly by adding new route to bottle
class HttpDaemon(object):
    def __init__(self):
        pass
    
    
    def run(self, addr, port, socket_path):
        # First enable cors on all our calls
        bapp = bottle.app()
        bapp.install(EnableCors())
        
        # Socket access got a root access, a direct one :)
        # but in the external should be an autorization
        bapp.install(ExternalHttpProtectionLookup())
        
        if socket_path:
            # Will lock for in this
            # warning: without the str() cherrypy is not happy with the value, do not emove it
            bapp.run(server='cherrypy', bind_addr=str(socket_path), numthreads=8)  # not need for a lot of threads here
        else:
            # And this too but in another thread
            bapp.run(host=addr, port=port, server='cherrypy', numthreads=64)  # 256?
    
    
    # Some default URI
    @error(404)
    def err404(error):
        return ''
    
    
    # Some default URI    
    @error(401)
    def err401(error):
        return ''
    
    
    @http_export('/')
    def slash():
        return 'OK'
    
    
    @http_export('/api')
    @http_export('/api/')
    def list_api():
        response.content_type = 'application/json'
        return json.dumps(exported_functions.values())


httpdaemon = HttpDaemon()
