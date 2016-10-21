import os
import copy
import traceback
import subprocess
import codecs
import stat
import shutil

try:
    import jinja2
except Exception, exp:
    jinja2 = None

from kunai.log import logger
from kunai.gossip import gossiper


# Get all nodes that are defining a service sname and where the service is OK
def ok_nodes(service=''):
    sname = service
    with gossiper.nodes_lock:
        nodes = copy.copy(gossiper.nodes)  # just copy the dict, not the nodes themselves
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
    def generate(self):
        # If not jinja2, bailing out
        if jinja2 is None:
            logger.debug('Generator: Error, no jinja2 librairy defined, please install it', part='generator')
            return
        try:
            f = open(self.g['template'], 'r')
            self.buf = f.read().decode('utf8', errors='ignore')
            f.close()
        except IOError, exp:
            logger.error('Cannot open template file %s : %s' % (self.g['template'], exp), part='generator')
            self.buf = None
            self.template = None
        
        # copy objects because they can move
        node = copy.copy(gossiper.nodes[gossiper.uuid])
        with gossiper.nodes_lock:
            nodes = copy.copy(gossiper.nodes)  # just copy the dict, not the nodes themselves
        
        # Now try to make it a jinja template object
        try:
            env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
        except TypeError:  # old jinja2 version do not manage keep_trailing_newline nor
            # lstrip_blocks (like in redhat6)
            env = jinja2.Environment(trim_blocks=True)
        
        try:
            self.template = env.from_string(self.buf)
        except Exception, exp:
            logger.error('Template file %s did raise an error with jinja2 : %s' % (self.g['template'], exp), part='generator')
            self.buf = None
            self.template = None
        
        # Now try to render all of this with real objects
        try:
            self.output = self.template.render(nodes=nodes, node=node, ok_nodes=ok_nodes)
        except Exception:
            logger.error('Template rendering %s did raise an error with jinja2 : %s' % (
                self.g['template'], traceback.format_exc()), part='generator')
            self.output = None
            self.template = None
            self.buf = None
        
        # if we have a partial generator prepare the output we must check for
        if self.output is not None and self.g['partial_start'] and self.g['partial_end']:
            self.output = '%s\n%s\n%s' % (self.g['partial_start'], self.output, self.g['partial_end'])
        logger.debug('Generator %s did generate output:\n%s' % (self.g['name'], self.output), part='generator')
    
    
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
                logger.error('Cannot open path file %s : %s' % (self.g['path'], exp), part='generator')
                self.output = None
                self.template = ''
                self.buf = ''
                return False
        
        need_regenerate_full = False
        need_regenerate_partial = False
        if not os.path.exists(self.g['path']):
            need_regenerate_full = True
        # if partial, just look for inclusion in the file data
        if (self.g['partial_start'] and self.g['partial_end']):
            if self.output not in self.cur_value:
                logger.info('Need to regenerate file %s with new data from generator %s' % (self.g['path'], self.g['name']))
                need_regenerate_partial = True
        else:  # not partial, must be equal to file
            if self.output != self.cur_value:
                need_regenerate_full = True
        
        # If not exists or the value did change, regenerate it :)
        if need_regenerate_full:
            logger.debug('Generator %s generate a new value, writing it to %s' % (self.g['name'], self.g['path']), part='generator')
            try:
                f = codecs.open(self.g['path'], "w", "utf-8")
                f.write(self.output)
                f.close()
                logger.log('Generator %s did generate a new file at %s' % (self.g['name'], self.g['path']), part='generator')
                return True
            except IOError, exp:
                logger.error('Cannot write path file %s : %s' % (self.g['path'], exp), part='generator')
                self.output = None
                self.template = ''
                self.buf = ''
                return False
        
        # If not exists or the value did change, regenerate it :)
        if need_regenerate_partial:
            logger.debug('Generator %s generate partial file writing it to %s' % (self.g['name'], self.g['path']), part='generator')
            try:
                f = codecs.open(self.g['path'], "r", "utf-8")
                orig_content = f.read()
                # As we will pslit lines and so lost the \n we should look if the last one was ending with one or not
                orig_content_finish_with_new_line = (orig_content[-1] == '\n')
                lines = orig_content.splitlines()
                logger.debug('ORIGIANL CONTENT: %s' % orig_content, part='generator')
                del orig_content
                f.close()
                # find the part to remove between start and end of the partial
                try:
                    idx_start = lines.index(self.g['partial_start'])
                except ValueError:  # not found?
                    idx_start = None
                try:
                    idx_end = lines.index(self.g['partial_end'])
                except ValueError:  # not found?
                    idx_end = None
                
                # Manage partial part not found, so maybe in the end
                if idx_start is None or idx_end is None:
                    if self.g['if_partial_missing'] == 'append':
                        part_before = lines
                        part_after = []
                        logger.debug('APPEND MODE: force a return line? %s' % orig_content_finish_with_new_line, part='generator')
                        # if the file did not finish with \n, force one
                        if not orig_content_finish_with_new_line:
                            part_before.append('\n')
                    else:
                        logger.error('The generator %s do not have a valid if_partial_missing property' % (self.g['name']), part='generator')
                        return False
                else:  # partial found, look at part before/after
                    # Maybe there is a bad order in the index?
                    if idx_start > idx_end:
                        logger.error('The partial_start "%s" and partial_end "%s" in the file "%s" for the generator %s are not in the good order' % (self.g['partial_start'], self.g['partial_end'], self.g['path'], self.g['name']), part='generator')
                        self.output = None
                        self.template = ''
                        self.buf = ''
                        return False
                    part_before = lines[:idx_start]
                    part_after = lines[idx_end+1:]
                last_char = '' if not orig_content_finish_with_new_line else '\n'
                new_content = '%s\n%s%s%s' % ('\n'.join(part_before), self.output, '\n'.join(part_after), last_char)
                logger.debug('Temporary file for partial replacement: %s and %s %s=>%s' % (part_before, part_after, idx_start, idx_end), part='generator')
                logger.debug('New content: %s' % new_content, part='generator')
                tmp_path = '%s.temporary-generator' % self.g['path']
                f2 = codecs.open(tmp_path, 'w', 'utf-8')
                f2.write(new_content)
                logger.debug('DID GENERATE: %s' % new_content)
                f2.close()
                # now the second file is ok, move it to the first one place, but with:
                # * same user/group
                # * same permissions
                prev_stats = os.stat(self.g['path'])
                prev_uid = prev_stats.st_uid
                prev_gid = prev_stats.st_gid
                os.chown(tmp_path, prev_uid, prev_gid)
                prev_permissions = prev_stats[stat.ST_MODE]
                logger.debug('PREV UID GID PERMISSIONS: %s %s %s' % (prev_uid, prev_gid, prev_permissions), part='generator')
                os.chmod(tmp_path, prev_permissions)
                logger.log('Generator %s did generate a new file at %s' % (self.g['name'], self.g['path']), part='generator')
                shutil.move(tmp_path, self.g['path'])
                return True
            except IOError, exp:
                logger.error('Cannot write path file %s : %s' % (self.g['path'], exp), part='generator')
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
            logger.error('Generator %s command launch (%s) fail : %s' % (self.g['name'], cmd, exp), part='generator')
            return
        output, err = p.communicate()
        rc = p.returncode
        if rc != 0:
            logger.error('Generator %s command launch (%s) error (rc=%s): %s' % (self.g['name'], cmd, rc, '\n'.join([output, err])), part='generator')
            return
        logger.debug("Generator %s command succeded" % self.g['name'], part='generator')
