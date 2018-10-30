#!/usr/bin/env python
import json
import os
import codecs

from .yamlmgr import yamler
from .log import LoggerFactory
from .httpdaemon import http_export, response

# Global logger for this part
logger = LoggerFactory.create_logger('packs')

# Pack directory levels, but beware: the order IS important
PACKS_LEVELS = ('core', 'global', 'zone', 'local')

class PackManager(object):
    def __init__(self):
        self.packs = {'core': {}, 'global': {}, 'zone': {}, 'local': {}}
        
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
    
    
    def get_pack_directory(self, pack_level, pack_name):
        try:
            return self.packs[pack_level][pack_name][1]
        except IndexError:  # no such pack
            return ''
    
    
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
                    with codecs.open(package_pth, 'r', encoding='utf8') as f:
                        package_buf = f.read()
                        package = yamler.loads(package_buf)
                        self.load_package(package, package_pth, level)
                except Exception as exp:  # todo: more precise catch? I think so
                    logger.error('Cannot load package %s: %s' % (package_pth, exp))
    
    
    # We want to have directories that we need to load, but there is a rule:
    # * local > zone > global for a same pack (based on name)
    def give_pack_directories_to_load(self):
        to_load_idx = set()  # used to know if we already see suck a pack
        to_load = {}
        for level in PACKS_LEVELS:
            for pname in self.packs[level]:
                if pname in to_load_idx:
                    logger.debug('Skipping pack %s/%s to load because it was already present in a more priority level' % (level, pname))
                    continue
                to_load_idx.add(pname)
                package_data, dir_name = self.packs[level][pname]
                to_load[pname] = (pname, level, dir_name)
        logger.debug('Directories to load: %s' % to_load.values())
        
        return to_load.values()
    
    
    def get_packs(self):
        return self.packs
    
    
    def get_pack_all_topics(self, pname):
        for level in PACKS_LEVELS:
            pack = self.packs[level].get(pname, None)
            if not pack:
                continue
            package, dir = pack
            topics = package.get('topics', [])[:]  # get a copy, do not direct link it
            return topics
        return []
    
    
    def get_pack_main_and_secondary_topics(self, pname):
        topics = self.get_pack_all_topics(pname)
        if not topics:
            return ('generic', [])
        return (topics[0], topics[1:])
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        @http_export('/packs/')
        @http_export('/packs')
        def get_packs():
            response.content_type = 'application/json'
            return json.dumps(self.packs)


packer = PackManager()
