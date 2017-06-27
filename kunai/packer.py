#!/usr/bin/env python
import json
from kunai.log import logger
from kunai.httpdaemon import http_export, response


class PackManager(object):
    def __init__(self):
        self.packs = {}
        
        # We got an object, we can fill the http daemon part
        self.export_http()
    
    
    def load_package(self, package, file_path):
        logger.debug('Loading package data from file %s' % file_path)
        pname = package.get('name', None)
        if pname is None:
            logger.error('Package data is missing name entry (%s)' % file_path)
            return None
        self.packs[pname] = package
        return pname
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        @http_export('/packs/')
        @http_export('/packs')
        def get_packs():
            response.content_type = 'application/json'
            return json.dumps(self.packs.values())


packer = PackManager()
