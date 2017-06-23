import os
import glob
import time
import shutil
import hashlib
import subprocess
import json

from kunai.log import logger
from kunai.pubsub import pubsub
from kunai.threadmgr import threader
from kunai.stop import stopper
from kunai.detectormgr import detecter
from kunai.gossip import gossiper
from kunai.kv import kvmgr


class ShinkenExporter(object):
    def __init__(self):
        self.regenerate_flag = False
        self.reload_flag = False
        self.cfg_path = None
        self.node_changes = []
        self.reload_command = ''
        # register to node events
        pubsub.sub('new-node', self.new_node_callback)
        pubsub.sub('delete-node', self.delete_node_callback)
        pubsub.sub('change-node', self.change_node_callback)
    
    
    def load_cfg_path(self, cfg_path):
        self.cfg_path = os.path.abspath(cfg_path)
    
    
    def load_reload_command(self, reload_command):
        self.reload_command = reload_command
    
    
    def launch_thread(self):
        # Launch a thread that will reap all put key asked by the udp
        self.shinken_thread = threader.create_and_launch(self.main_thread, name='shinken-exporter', essential=True)
    
    
    def new_node_callback(self, node_uuid=None):
        self.node_changes.append(('new-node', node_uuid))
        self.regenerate_flag = True
    
    
    def delete_node_callback(self, node_uuid=None):
        self.node_changes.append(('delete-node', node_uuid))
        self.regenerate_flag = True
    
    
    def change_node_callback(self, node_uuid=None):
        self.node_changes.append(('change-node', node_uuid))
        self.regenerate_flag = True
    
    
    def sanatize_check_name(self, cname):
        return 'Agent-%s' % cname.split('/')[-1]
    
    
    def export_states_into_shinken(self, nuuid):
        p = '/var/lib/shinken/nagios.cmd'
        if not os.path.exists(p):
            logger.error('Shinken command file is missing, skipping node information export')
            return
        
        v = kvmgr.get_key('__health/%s' % nuuid)
        if v is None or v == '':
            logger.error('Cannot access to the checks list for', nuuid, part='shinken')
            return
        
        lst = json.loads(v)
        for cname in lst:
            v = kvmgr.get_key('__health/%s/%s' % (nuuid, cname))
            if v is None:  # missing check entry? not a real problem
                continue
            check = json.loads(v)
            logger.debug('CHECK VALUE %s' % check, part='shinken')
            try:
                f = open(p, 'a')
                cmd = '[%s] PROCESS_SERVICE_CHECK_RESULT;%s;%s;%d;%s\n' % (int(time.time()), nuuid, self.sanatize_check_name(cname), check['state_id'], check['output'])
                logger.debug('SAVING COMMAND %s' % cmd, part='shinken')
                f.write(cmd)
                f.flush()
                f.close()
            except Exception, exp:
                logger.error('Shinken command file write fail: %s' % exp)
                return
    
    
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
                print self.cfg_path
                print exp
                logger.error('Cannot create shinken directory at %s : %s', self.cfg_path, str(exp), part='shinken')
                return
        logger.debug('Generating cfg/sha file for node %s' % n, part='shinken')
        p, shap = self.__get_node_cfg_sha_paths(uuid)
        # p = os.path.join(self.cfg_path, uuid + '.cfg')
        ptmp = p + '.tmp'
        # shap = os.path.join(self.cfg_path, uuid + '.sha1')
        shaptmp = shap + '.tmp'
        
        old_sha_value = ''
        if os.path.exists(shap):
            try:
                f = open(shap, 'r')
                old_sha_value = f.read().strip()
                f.close()
            except Exception, exp:
                logger.error('Cannot read old sha file value at %s: %s' % (shap, exp))
        
        tpls = n.get('tags', [])[:]  # make a copy, because we will modify it
        zone = n.get('zone', '')
        if zone:
            tpls.append(zone)
        tpls.insert(0, 'agent,kunai')
        
        # get checks names and sort them so file il always the same
        cnames = n.get('checks', {}).keys()
        cnames.sort()
        
        # Services must be purely passive, and will only trigger once
        buf_service = '''define service{
            host_name               %s
            service_description     %s
            use                     generic-service
            active_checks_enabled   0
            passive_checks_enabled  1
            check_command           _echo
            max_check_attempts      1
        \n}\n
        '''
        
        buf = '''# Auto generated host, do not edit
        \ndefine host{
            host_name      %s
            display_name   %s
            address        %s
            use            %s
        \n}\n
        \n%s\n''' % (n['uuid'], n['name'], n['addr'], ','.join(tpls), '\n'.join([buf_service % (n['uuid'], self.sanatize_check_name(cname)) for cname in cnames]))
        buf_sha = hashlib.sha1(buf).hexdigest()
        
        # if it the same as before?
        logger.debug('COMPARING OLD SHA/NEWSHA= %s   %s' % (old_sha_value, buf_sha), part='shinken')
        if buf_sha == old_sha_value:
            logger.debug('SAME SHA VALUE, SKIP IT', part='shinken')
            return
        
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
        # We did change configuration, reload shinken
        self.reload_flag = True
    
    
    # A specific node id was detected as not need, try to clean it
    def clean_node_files(self, nid):
        cfgp, shap = self.__get_node_cfg_sha_paths(nid)
        if os.path.exists(cfgp):
            try:
                os.unlink(cfgp)
                # We did remove a file, reload shinken so
                self.reload_flag = True
            except IOError, exp:
                logger.error('Cannot remove deprecated file %s' % cfgp, part='shinken')
        if os.path.exists(shap):
            try:
                os.unlink(shap)
            except IOError, exp:
                logger.error('Cannot remove deprecated file %s' % shap, part='shinken')
    
    
    def clean_cfg_dir(self):
        if not self.cfg_path:  # nothing to clean...
            return
        node_keys = gossiper.nodes.keys()
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
        
        # If the detector did not run, we are not sure about the tags of the local node
        # so wait for it to be run, so we can generate shinken file ok from start
        while detecter.did_run == False:
            time.sleep(1)
        
        if self.cfg_path is not None:
            self.clean_cfg_dir()
            # First look at all nodes in the gossip ring and regerate them
            node_keys = gossiper.nodes.keys()
            for nid in node_keys:
                n = gossiper.get(nid)
                if n is None:
                    continue
                self.generate_node_file(n)
        
        while not stopper.interrupted:
            logger.debug('Shinken loop, regenerate [%s]' % self.regenerate_flag, part='shinken')
            
            time.sleep(1)
            # If not initialize, skip loop
            if self.cfg_path is None or gossiper is None:
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
                n = gossiper.get(nid)
                if evt == 'new-node':
                    if n is None:  # maybe someone just delete the node?
                        continue
                    logger.info('Manage new node %s' % n, part='shinken')
                    self.generate_node_file(n)
                    self.export_states_into_shinken(nid)  # update it's inner checks states
                elif evt == 'delete-node':
                    logger.info('Removing deleted node %s' % nid, part='shinken')
                    self.clean_node_files(nid)
                elif evt == 'change-node':
                    logger.info('A node did change, updating its configuration. Node %s' % nid, part='shinken')
                    self.generate_node_file(n)
                    self.export_states_into_shinken(nid)  # update it's inner checks states
            
            # If we need to reload and have a reload commmand, do it
            if self.reload_flag and self.reload_command:
                self.reload_flag = False
                p = subprocess.Popen(self.reload_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     close_fds=True, preexec_fn=os.setsid)
                stdout, stderr = p.communicate()
                stdout += stderr
                if p.returncode != 0:
                    logger.error('Cannot reload shinken daemon: %s' % stdout, part='shinken')
                else:
                    logger.info('Shinken daemon reload: OK')


shinkenexporter = ShinkenExporter()
