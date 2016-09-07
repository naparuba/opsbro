import os
import glob
import time
import shutil
import hashlib
from kunai.log import logger
from kunai.pubsub import pubsub
from kunai.threadmgr import threader
from kunai.stop import stopper


class ShinkenExporter(object):
    def __init__(self):
        self.regenerate_flag = False
        self.cfg_path = None
        self.node_changes = []
        self.gossiper = None
        # register to node events
        pubsub.sub('new-node', self.new_node_callback)
        pubsub.sub('delete-node', self.delete_node_callback)
    
    
    def load_cfg_path(self, cfg_path):
        self.cfg_path = os.path.abspath(cfg_path)
    
    
    def load_gossiper(self, gossiper):
        self.gossiper = gossiper
    
    
    def launch_thread(self):
        # Launch a thread that will reap all put key asked by the udp
        self.shinken_thread = threader.create_and_launch(self.main_thread, name='shinken-exporter')
    
    
    def new_node_callback(self, node_uuid=None):
        self.node_changes.append(('new-node', node_uuid))
        self.regenerate_flag = True
    
    
    def delete_node_callback(self, node_uuid=None):
        self.node_changes.append(('delete-node', node_uuid))
        self.regenerate_flag = True
    
    
    def __get_node_cfg_sha_paths(self, nid):
        cfg_p = os.path.join(self.cfg_path, nid + '.cfg')
        sha_p = os.path.join(self.cfg_path, nid + '.sha1')
        return (cfg_p, sha_p)
    
    
    def generate_node_file(self, n):
        uuid = n.get('uuid')
        if not os.path.exists(self.cfg_path):
            try:
                os.mkdir(self.cfg_path)
            except Exception, exp:
                logger.error('Cannot create shinken directory at %s : %s' % (self.cfg_path, exp), part='shinken')
                return
        logger.debug('Generating cfg/sha file for node %s' % n, part='shinken')
        p, shap = self.__get_node_cfg_sha_paths(uuid)
        # p = os.path.join(self.cfg_path, uuid + '.cfg')
        ptmp = p + '.tmp'
        # shap = os.path.join(self.cfg_path, uuid + '.sha1')
        shaptmp = shap + '.tmp'
        tpls = n.get('tags', [])
        zone = n.get('zone', '')
        if zone:
            tpls.append(zone)
        
        buf = '''define host{
            host_name      %s
            display_name   %s
            address        %s
            use            %s
        }\n''' % (n['uuid'], n['name'], n['addr'], ','.join(tpls))
        buf_sha = hashlib.sha1(buf).hexdigest()
        logger.info('Will generate in path %s (sha1=%s): \n%s' % (p, buf_sha, buf), part='shinken')
        try:
            # open both file, so if one goes wrong, will be consistent
            fcfg = open(ptmp, 'w')
            fsha = open(shaptmp, 'w')
            # save cfg file
            fcfg.write(buf)
            fcfg.close()
            shutil.move(ptmp, p)
            # and then sha one
            fsha.write(buf_sha)
            fsha.close()
            shutil.move(shaptmp, shap)
        except IOError, exp:
            try:
                fcfg.close()
            except:
                pass
            try:
                fsha.close()
            except:
                pass
            logger.error('Cannot create shinken node file at %s : %s' % (p, exp), part='shinken')
            return
        logger.info('Generated file %s for node %s' % (p, uuid), part='shinken')
    
    
    # A specific node id was detected as not need, try to clean it
    def clean_node_files(self, nid):
        cfgp, shap = self.__get_node_cfg_sha_paths(nid)
        if os.path.exists(cfgp):
            try:
                os.unlink(cfgp)
            except IOError, exp:
                logger.error('Cannot remove deprecated file %s' % cfgp, part='shinken')
        if os.path.exists(shap):
            try:
                os.unlink(shap)
            except IOError, exp:
                logger.error('Cannot remove deprecated file %s' % shap, part='shinken')
    
    
    def clean_cfg_dir(self):
        node_keys = self.gossiper.nodes.keys()
        logger.debug('Current nodes uuids: %s' % node_keys, part='shinken')
        # First look at cfg file that don't match our inner elements, based on their file name
        # Note: if the user did do something silly, no luck for him!
        cfgs = glob.glob('%s/*.cfg' % self.cfg_path)
        logger.info('Looking at files for cleaning %s' % cfgs, part='shinken')
        lpath = len(self.cfg_path) + 1
        for cfg in cfgs:
            fuuid_ = cfg[lpath:-len('.cfg')]  # get only the uuid part of the file name
            logger.debug('Should we clean cfg file %s' % fuuid_, part='shinken')
            if fuuid_ not in node_keys:
                logger.info('We clean deprecated cfg file %s' % cfg, part='shinken')
                self.clean_node_files(fuuid_)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def main_thread(self):
        self.clean_cfg_dir()
        # First look at all nodes in the cluster and regerate them
        node_keys = self.gossiper.nodes.keys()
        for nid in node_keys:
            n = self.gossiper.nodes.get(nid, None)
            if n is None:
                continue
            self.generate_node_file(n)
        
        while not stopper.interrupted:
            logger.debug('Shinken loop, regenerate [%s]' % self.regenerate_flag, part='shinken')
            time.sleep(1)
            # If not initialize, skip loop
            if self.cfg_path is None or self.gossiper is None:
                continue
            # If nothing to do, skip it too
            if not self.regenerate_flag:
                continue
            logger.info('Shinken callback raised, managing events: %s' % self.node_changes, part='shinken')
            # Set that we will manage all now
            self.regenerate_flag = False
            node_ids = self.node_changes
            self.node_changes = []
            for (evt, nid) in node_ids:
                n = self.gossiper.nodes.get(nid, None)
                if evt == 'new-node':
                    if n is None:  # maybe someone just delete the node?
                        continue
                    logger.info('Manage new node %s' % n, part='shinken')
                    self.generate_node_file(n)
                elif evt == 'delete-node':
                    logger.info('Removing deleted node %s' % nid, part='shinken')
                    self.clean_node_files(nid)


shinkenexporter = ShinkenExporter()
