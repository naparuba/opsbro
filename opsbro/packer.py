#!/usr/bin/env python
import json
import os
from opsbro.yamlmgr import yamler
from opsbro.log import LoggerFactory
from opsbro.httpdaemon import http_export, response

# Global logger for this part
logger = LoggerFactory.create_logger('packs')


class PackManager(object):
    def __init__(self):
        self.packs = {'global': {}, 'zone': {}, 'local': {}}
        
        # We got an object, we can fill the http daemon part
        self.export_http()
    
    
    def load_package(self, package, file_path, level):
        if level not in self.packs:
            logger.error('Trying to load a pack from %s from an unknown level: %s' % (file_path, level))
            return None
        logger.debug('Loading package data from file %s' % file_path)
        pname = package.get('name', None)
        if pname is None:
            logger.error('Package data is missing name entry (%s)' % file_path)
            return None
        self.packs[level][pname] = (package, os.path.dirname(file_path))
    
    
    def load_pack_descriptions(self, root_dir, level):
        logger.debug('Loading packs directory under: %s' % root_dir)
        pack_dir = os.path.join(root_dir, 'packs')
        if not os.path.exists(pack_dir):
            return
        sub_dirs = [os.path.join(pack_dir, dname) for dname in os.listdir(pack_dir) if os.path.isdir(os.path.join(pack_dir, dname))]
        logger.debug('Loading packs directories : %s' % sub_dirs)
        # Look at collectors
        for pname in sub_dirs:
            # First load meta data from the package.json file (if present)
            package_pth = os.path.join(pname, 'package.yml')
            if os.path.exists(package_pth):
                try:
                    with open(package_pth, 'r') as f:
                        package_buf = f.read()
                        package = yamler.loads(package_buf)
                        self.load_package(package, package_pth, level)
                except Exception, exp:  # todo: more precise catch? I think so
                    logger.error('Cannot load package %s: %s' % (package_pth, exp))
    
    
    # We want to have directories that we need to load, but there is a rule:
    # * local > zone > global for a same pack (based on name)
    def give_pack_directories_to_load(self):
        to_load = {}
        for level in ('local', 'zone', 'global'):
            for pname in self.packs[level]:
                if pname in to_load:
                    logger.debug('Skipping pack %s/%s to load because it was already present in a more priority level' % (level, pname))
                    continue
                package_data, dir_name = self.packs[level][pname]
                to_load[pname] = dir_name
        logger.debug('Directories to load: %s' % to_load.values())
        
        return list(to_load.iteritems())
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        @http_export('/packs/')
        @http_export('/packs')
        def get_packs():
            response.content_type = 'application/json'
            return json.dumps(self.packs)


packer = PackManager()
