import os
import copy
import traceback
import subprocess
import codecs

try:
    import jinja2
except Exception, exp:
    jinja2 = None

from kunai.log import logger
from kunai.gossip import gossiper

gclust = None


# Get all nodes that are defining a service sname and where the service is OK
def ok_nodes(service=''):
    global gclust
    sname = service
    with gossiper.nodes_lock:
        nodes = copy.copy(gclust.nodes)  # just copy the dict, not the nodes themselves
    res = []
    for n in nodes.values():
        if n['state'] != 'alive':
            continue
        for s in n['services'].values():
            if s['name'] == sname and s['state_id'] == 0:
                res.append((n, s))
    return res


class Generator(object):
    def __init__(self, g):
        self.g = g
        self.buf = None
        self.template = None
        self.output = None
    
    
    # Open the template file and generate the output
    def generate(self, clust):
        # HACK, atomise this global thing!!
        global gclust
        gclust = clust
        # If not jinja2, bailing out
        if jinja2 is None:
            logger.debug('Generator: Error, no jinja2 librairy defined, please install it', part='generator')
            return
        try:
            f = open(self.g['template'], 'r')
            self.buf = f.read().decode('utf8', errors='ignore')
            f.close()
        except IOError, exp:
            logger.error('Cannot open template file %s : %s' % (self.g['template'], exp))
            self.buf = None
            self.template = None
        
        # copy objects because they can move
        node = copy.copy(clust.nodes[clust.uuid])
        with gossiper.nodes_lock:
            nodes = copy.copy(clust.nodes)  # just copy the dict, not the nodes themselves
        
        # Now try to make it a jinja template object
        try:
            env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
        except TypeError:  # old jinja2 version do not manage keep_trailing_newline nor
            # lstrip_blocks (like in redhat6)
            env = jinja2.Environment(trim_blocks=True)
        
        try:
            self.template = env.from_string(self.buf)
        except Exception, exp:
            logger.error('Template file %s did raise an error with jinja2 : %s' % (self.g['template'], exp))
            self.buf = None
            self.template = None
        
        # Now try to render all of this with real objects
        try:
            self.output = self.template.render(nodes=nodes, node=node, ok_nodes=ok_nodes)
        except Exception:
            logger.error('Template rendering %s did raise an error with jinja2 : %s' % (
                self.g['template'], traceback.format_exc()))
            self.output = None
            self.template = None
            self.buf = None
    
    
    # If we did generate, try to see if we must write the file, and if so we will have to
    # launch the command
    def write_if_need(self):
        # Maybe there is no output, if so bail out now :)
        if self.output is None:
            return False
        
        self.cur_value = ''
        # first try to load the current file if exist and compare to the generated file
        if os.path.exists(self.g['path']):
            try:
                f = codecs.open(self.g['path'], "r", "utf-8")
                self.cur_value = f.read()
                f.close()
            except IOError, exp:
                logger.error('Cannot open path file %s : %s' % (self.g['path'], exp))
                self.output = None
                self.template = ''
                self.buf = ''
                return False
        
        # If not exists or the value did change, regenerate it :)
        if not os.path.exists(self.g['path']) or self.cur_value != self.output:
            logger.debug('Generator %s generate a new value, writing it to %s' % (self.g['name'], self.g['path']))
            try:
                f = codecs.open(self.g['path'], "w", "utf-8")
                f.write(self.output)
                f.close()
                logger.log('Generator %s did generate a new file at %s' % (self.g['name'], self.g['path']))
                return True
            except IOError, exp:
                logger.error('Cannot write path file %s : %s' % (self.g['path'], exp))
                self.output = None
                self.template = ''
                self.buf = ''
                return False
    
    
    # If need launch the restart command, shoul not block too long of
    # course
    def launch_command(self):
        cmd = self.g.get('command', '')
        if not cmd:
            return
        try:
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                                 preexec_fn=os.setsid)
        except Exception, exp:
            logger.error('Generator %s command launch (%s) fail : %s' % (self.g['name'], cmd, exp))
            return
        output, err = p.communicate()
        rc = p.returncode
        if rc != 0:
            logger.error('Generator %s command launch (%s) error (rc=%s): %s' % (
                self.g['name'], cmd, rc, '\n'.join([output, err])))
            return
        logger.debug("Generator %s command succeded" % self.g['name'])
