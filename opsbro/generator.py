import os
import traceback
import codecs
import stat
import shutil

from .log import LoggerFactory
from .gossip import gossiper
from .library import libstore
from .evaluater import evaluater
from .util import unified_diff, exec_command, PY3

# Global logger for this part
logger = LoggerFactory.create_logger('generator')

GENERATOR_STATES = ['COMPLIANT', 'ERROR', 'UNKNOWN', 'NOT-ELIGIBLE']
GENERATOR_STATE_COLORS = {'COMPLIANT': 'green', 'ERROR': 'red', 'UNKNOWN': 'grey', 'NOT-ELIGIBLE': 'grey'}


class NoElementsExceptions(Exception):
    pass


class Generator(object):
    def __init__(self, g):
        self.g = g
        self.name = g['name']
        self.pack_name = g['pack_name']
        self.pack_level = g['pack_level']
        
        self.buf = None
        self.template = None
        self.output = None
        self.jinja2 = None
        self.generate_if = g['generate_if']
        self.cur_value = ''
        self.current_diff = []
        
        self.log = ''
        self.__state = 'UNKNOWN'
        self.__old_state = 'UNKNOWN'
        self.__did_change = False
    
    
    def __set_state(self, state):
        if self.__state == state:
            return
        
        self.__did_change = True
        self.__old_state = self.__state
        self.__state = state
        logger.debug('Compliance rule %s switch from %s to %s' % (self.name, self.__old_state, self.__state))
    
    
    def get_state(self):
        return self.__state
    
    
    def set_error(self, log):
        self.__set_state('ERROR')
        self.log = log
    
    
    def set_compliant(self, log):
        self.log = log
        logger.info(log)
        self.__set_state('COMPLIANT')
    
    
    def set_not_eligible(self):
        self.log = ''
        self.__set_state('NOT-ELIGIBLE')
    
    
    def get_json_dump(self):
        return {'name': self.name, 'state': self.__state, 'old_state': self.__old_state, 'log': self.log, 'pack_level': self.pack_level, 'pack_name': self.pack_name, 'diff': self.current_diff, 'path': self.g['path']}
    
    
    def get_history_entry(self):
        if not self.__did_change:
            return None
        return self.get_json_dump()
    
    
    def must_be_launched(self):
        self.__did_change = False
        try:
            b = evaluater.eval_expr(self.generate_if)
        except Exception as exp:
            err = ' (%s) if rule (%s) evaluation did fail: %s' % (self.name, self.generate_if, exp)
            self.set_error(err)
            logger.error(err)
            return False
        if not b:
            self.set_not_eligible()
        return b
    
    
    # Open the template file and generate the output
    def generate(self):
        if self.jinja2 is None:
            self.jinja2 = libstore.get_jinja2()
        
        # If not jinja2, bailing out
        if self.jinja2 is None:
            self.set_error('Generator: Error, no jinja2 librairy defined, please install it')
            return
        try:
            f = codecs.open(self.g['template'], 'r', 'utf8')
            self.buf = f.read()
            f.close()
        except IOError as exp:
            self.set_error('Cannot open template file %s : %s' % (self.g['template'], exp))
            self.buf = None
            self.template = None
            return
        
        # NOTE: nodes is a static object, node too (or atomic change)
        node = gossiper.nodes[gossiper.uuid]
        
        # Now try to make it a jinja template object
        try:
            env = self.jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
        except TypeError:  # old jinja2 version do not manage keep_trailing_newline nor
            # lstrip_blocks (like in redhat6)
            env = self.jinja2.Environment(trim_blocks=True)
        
        try:
            self.template = env.from_string(self.buf)
        except Exception as exp:
            self.set_error('Template file %s did raise an error with jinja2 : %s' % (self.g['template'], exp))
            self.output = None
            self.template = None
            self.buf = None
            return
        
        # Now try to render all of this with real objects
        try:
            self.output = self.template.render(nodes=gossiper.nodes, node=node, **evaluater.get_all_functions())
        except NoElementsExceptions:
            self.set_error('No nodes did match filters for template : %s %s' % (self.g['template'], self.name))
            self.output = None
            self.template = None
            self.buf = None
            return
        except Exception:
            self.set_error('Template rendering %s did raise an error with jinja2 : %s' % (self.g['template'], traceback.format_exc()))
            self.output = None
            self.template = None
            self.buf = None
            return
        
        # if we have a partial generator prepare the output we must check for
        if self.output is not None and self.g['partial_start'] and self.g['partial_end']:
            self.output = '%s\n%s\n%s\n' % (self.g['partial_start'], self.output, self.g['partial_end'])
        logger.debug('Generator %s did generate output:\n%s' % (self.g['name'], self.output))
    
    
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
            except IOError as exp:
                self.set_error('Cannot open path file %s : %s' % (self.g['path'], exp))
                self.output = None
                self.template = ''
                self.buf = ''
                self.current_diff = []
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
            logger.debug('Generator %s generate a new value, writing it to %s' % (self.g['name'], self.g['path']))
            try:
                self.current_diff = unified_diff(self.cur_value, self.output, self.g['path'])
                logger.info(u'FULL diff: %s' % u'\n'.join(self.current_diff))
                f = codecs.open(self.g['path'], "w", "utf-8")
                f.write(self.output)
                f.close()
                logger.info('Regenerate result: %s' % self.output)
                self.set_compliant('Generator %s did generate a new file at %s' % (self.g['name'], self.g['path']))
                return True
            except IOError as exp:
                self.set_error('Cannot write path file %s : %s' % (self.g['path'], exp))
                self.output = None
                self.template = ''
                self.buf = ''
                self.current_diff = []
                return False
        
        # If not exists or the value did change, regenerate it :)
        if need_regenerate_partial:
            logger.debug('Generator %s generate partial file writing it to %s' % (self.g['name'], self.g['path']))
            try:
                f = codecs.open(self.g['path'], "r", "utf-8")
                orig_content = f.read()
                # As we will pslit lines and so lost the \n we should look if the last one was ending with one or not
                orig_content_finish_with_new_line = (orig_content[-1] == '\n')
                lines = orig_content.splitlines()
                logger.debug('ORIGINLL CONTENT: %s' % orig_content)
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
                        logger.debug('APPEND MODE: force a return line? %s' % orig_content_finish_with_new_line)
                        # if the file did not finish with \n, force one
                        if not orig_content_finish_with_new_line:
                            part_before.append('\n')
                    else:
                        self.set_error('The generator %s do not have a valid if_partial_missing property' % (self.g['name']))
                        return False
                else:  # partial found, look at part before/after
                    # Maybe there is a bad order in the index?
                    if idx_start > idx_end:
                        self.set_error('The partial_start "%s" and partial_end "%s" in the file "%s" for the generator %s are not in the good order' % (self.g['partial_start'], self.g['partial_end'], self.g['path'], self.g['name']))
                        self.output = None
                        self.template = ''
                        self.buf = ''
                        self.current_diff = []
                        return False
                    part_before = lines[:idx_start]
                    part_after = lines[idx_end + 1:]
                last_char = '' if not orig_content_finish_with_new_line else '\n'
                new_content = '%s\n%s%s%s' % ('\n'.join(part_before), self.output, '\n'.join(part_after), last_char)
                
                self.current_diff = unified_diff(self.cur_value, new_content, self.g['path'])
                
                logger.debug('Temporary file for partial replacement: %s and %s %s=>%s' % (part_before, part_after, idx_start, idx_end))
                logger.debug('New content: %s' % new_content)
                logger.info(u'DIFF content: %s' % u'\n'.join(self.current_diff))
                
                tmp_path = '%s.temporary-generator' % self.g['path']
                f2 = codecs.open(tmp_path, 'w', 'utf-8')
                f2.write(new_content)
                logger.info('DID GENERATE NEW CONTENT: %s' % new_content)
                f2.close()
                # now the second file is ok, move it to the first one place, but with:
                # * same user/group
                # * same permissions
                prev_stats = os.stat(self.g['path'])
                prev_uid = prev_stats.st_uid
                prev_gid = prev_stats.st_gid
                os.chown(tmp_path, prev_uid, prev_gid)
                prev_permissions = prev_stats[stat.ST_MODE]
                logger.debug('PREV UID GID PERMISSIONS: %s %s %s' % (prev_uid, prev_gid, prev_permissions))
                os.chmod(tmp_path, prev_permissions)
                shutil.move(tmp_path, self.g['path'])
                self.set_compliant('Generator %s did generate a new file at %s' % (self.g['name'], self.g['path']))
                return True
            except IOError as exp:
                self.set_error('Cannot write path file %s : %s' % (self.g['path'], exp))
                self.output = None
                self.template = ''
                self.buf = ''
                self.current_diff = []
                return False
    
    
    # If need launch the restart command, shoul not block too long of
    # course
    def launch_command(self):
        cmd = self.g.get('command', '')
        if not cmd:
            return
        
        try:
            rc, output, err = exec_command(cmd)
        except Exception as exp:
            self.set_error('Generator %s command launch (%s) fail : %s' % (self.g['name'], cmd, exp))
            return
        if rc != 0:
            self.set_error('Generator %s command launch (%s) error (rc=%s): %s' % (self.g['name'], cmd, rc, '\n'.join([output, err])))
            return
        logger.info('Generator %s command launch (%s) SUCCESS (rc=%s): %s' % (self.g['name'], cmd, rc, '\n'.join([output, err])))
