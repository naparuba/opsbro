import os
import glob
import time
import shutil
import hashlib
import subprocess
import json

from opsbro.module import ConnectorModule
from opsbro.parameters import StringParameter, BoolParameter
from opsbro.pubsub import pubsub
from opsbro.threadmgr import threader
from opsbro.stop import stopper
from opsbro.detectormgr import detecter
from opsbro.gossip import gossiper
from opsbro.kv import kvmgr


class ShinkenModule(ConnectorModule):
    implement = 'shinken'
    
    parameters = {
        'enabled'              : BoolParameter(default=False),
        'cfg_path'             : StringParameter(default='/etc/shinken/agent'),
        'reload_command'       : StringParameter(default='/etc/init.d/shinken reload'),
        'monitoring_tool'      : StringParameter(default='shinken'),
        'external_command_file': StringParameter(default='/var/lib/shinken/shinken.cmd'),
    }
    
    
    def __init__(self):
        ConnectorModule.__init__(self)
        self.regenerate_flag = False
        self.reload_flag = False
        self.cfg_path = None
        self.node_changes = []
        self.reload_command = ''
        self.monitoring_tool = 'shinken'
        self.external_command_file = '/var/lib/shinken/shinken.cmd'
    
    
    def prepare(self):
        self.logger.info('SHINKEN: prepare phase')
        self.cfg_path = os.path.abspath(self.get_parameter('cfg_path'))
        self.reload_command = self.get_parameter('reload_command')
        self.monitoring_tool = self.get_parameter('monitoring_tool')
        self.external_command_file = self.get_parameter('external_command_file')
        # register to node events
        pubsub.sub('new-node', self.new_node_callback)
        pubsub.sub('delete-node', self.delete_node_callback)
        pubsub.sub('change-node', self.change_node_callback)
    
    
    def launch(self):
        self.shinken_thread = threader.create_and_launch(self.main_thread, name='Export nodes/checks and states to Shinken', essential=True, part='shinken')
    
    
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
        p = self.external_command_file
        if not os.path.exists(p):
            self.logger.info('Shinken command file %s is missing, skipping node information export' % p)
            return
        
        v = kvmgr.get_key('__health/%s' % nuuid)
        if v is None or v == '':
            self.logger.error('Cannot access to the checks list for', nuuid)
            return
        
        lst = json.loads(v)
        for cname in lst:
            v = kvmgr.get_key('__health/%s/%s' % (nuuid, cname))
            if v is None:  # missing check entry? not a real problem
                continue
            check = json.loads(v)
            self.logger.debug('CHECK VALUE %s' % check)
            try:
                f = open(p, 'a')
                cmd = '[%s] PROCESS_SERVICE_CHECK_RESULT;%s;%s;%d;%s\n' % (int(time.time()), nuuid, self.sanatize_check_name(cname), check['state_id'], check['output'])
                self.logger.debug('SAVING COMMAND %s' % cmd)
                f.write(cmd)
                f.flush()
                f.close()
            except Exception, exp:
                self.logger.error('Shinken command file write fail: %s' % exp)
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
                self.logger.error('Cannot create shinken directory at %s : %s', self.cfg_path, str(exp))
                return
        self.logger.debug('Generating cfg/sha file for node %s' % n)
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
                self.logger.error('Cannot read old sha file value at %s: %s' % (shap, exp))
        
        tpls = n.get('groups', [])[:]  # make a copy, because we will modify it
        zone = n.get('zone', '')
        if zone:
            tpls.append(zone)
        tpls.insert(0, 'agent,opsbro')
        
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
            check_command           check-host-alive
            max_check_attempts      1
        \n}\n
        '''
        # NOTE: nagios is not liking templates that are not exiting, so only export with generic-host
        # shinken don't care, so we can give all we want here
        use_value = ','.join(tpls)
        if self.monitoring_tool == 'nagios':
            use_value = 'generic-host'
        
        buf = '''# Auto generated host, do not edit
        \ndefine host{
            host_name      %s
            display_name   %s
            address        %s
            use            %s
            check_period                    24x7
            check_interval                  1
            retry_interval                  1
            max_check_attempts              2
        \n}\n
        \n%s\n''' % (n['uuid'], n['name'], n['addr'], use_value, '\n'.join([buf_service % (n['uuid'], self.sanatize_check_name(cname)) for cname in cnames]))
        buf_sha = hashlib.sha1(buf).hexdigest()
        
        # if it the same as before?
        self.logger.debug('COMPARING OLD SHA/NEWSHA= %s   %s' % (old_sha_value, buf_sha))
        if buf_sha == old_sha_value:
            self.logger.debug('SAME SHA VALUE, SKIP IT')
            return
        
        self.logger.info('Will generate in path %s (sha1=%s): \n%s' % (p, buf_sha, buf))
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
            self.logger.error('Cannot create shinken node file at %s : %s' % (p, exp))
            return
        self.logger.info('Generated file %s for node %s' % (p, uuid))
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
                self.logger.error('Cannot remove deprecated file %s' % cfgp)
        if os.path.exists(shap):
            try:
                os.unlink(shap)
            except IOError, exp:
                self.logger.error('Cannot remove deprecated file %s' % shap)
    
    
    def clean_cfg_dir(self):
        if not self.cfg_path:  # nothing to clean...
            return
        node_keys = gossiper.nodes.keys()
        self.logger.debug('Current nodes uuids: %s' % node_keys)
        # First look at cfg file that don't match our inner elements, based on their file name
        # Note: if the user did do something silly, no luck for him!
        cfgs = glob.glob('%s/*.cfg' % self.cfg_path)
        self.logger.info('Looking at files for cleaning %s' % cfgs)
        lpath = len(self.cfg_path) + 1
        for cfg in cfgs:
            fuuid_ = cfg[lpath:-len('.cfg')]  # get only the uuid part of the file name
            self.logger.debug('Should we clean cfg file %s' % fuuid_)
            if fuuid_ not in node_keys:
                self.logger.info('We clean deprecated cfg file %s' % cfg)
                self.clean_node_files(fuuid_)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def main_thread(self):
        
        # If the detector did not run, we are not sure about the groups of the local node
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
            self.logger.debug('Shinken loop, regenerate [%s]' % self.regenerate_flag)
            
            time.sleep(1)
            # If not initialize, skip loop
            if self.cfg_path is None or gossiper is None:
                continue
            # If nothing to do, skip it too
            if not self.regenerate_flag:
                continue
            self.logger.info('Shinken callback raised, managing events: %s' % self.node_changes)
            # Set that we will manage all now
            self.regenerate_flag = False
            node_ids = self.node_changes
            self.node_changes = []
            for (evt, nid) in node_ids:
                n = gossiper.get(nid)
                if evt == 'new-node':
                    if n is None:  # maybe someone just delete the node?
                        continue
                    self.logger.info('Manage new node %s' % n)
                    self.generate_node_file(n)
                    self.export_states_into_shinken(nid)  # update it's inner checks states
                elif evt == 'delete-node':
                    self.logger.info('Removing deleted node %s' % nid)
                    self.clean_node_files(nid)
                elif evt == 'change-node':
                    self.logger.info('A node did change, updating its configuration. Node %s' % nid)
                    self.generate_node_file(n)
                    self.export_states_into_shinken(nid)  # update it's inner checks states
            
            # If we need to reload and have a reload commmand, do it
            if self.reload_flag and self.reload_command:
                self.reload_flag = False
                p = subprocess.Popen(self.reload_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, preexec_fn=os.setsid)
                stdout, stderr = p.communicate()
                stdout += stderr
                if p.returncode != 0:
                    self.logger.error('Cannot reload monitoring daemon: %s' % stdout)
                else:
                    self.logger.info('Monitoring daemon reload: OK')
