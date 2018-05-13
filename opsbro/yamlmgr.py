import os
import sys
import shutil
import datetime
import time

from .characters import CHARACTERS
import opsbro.misc
from .library import libstore


p = os.path.join(os.path.dirname(opsbro.misc.__file__), 'internalyaml')
sys.path.insert(0, p)

import ruamel.yaml as yaml

from .log import LoggerFactory

logger = LoggerFactory.create_logger('yaml')

ENDING_SUFFIX = '#___ENDING___'


# Class to wrap several things to json, like manage some utf8 things and such things
class YamlMgr(object):
    def __init__(self):
        # To allow some libs to directly call ruaml.yaml. FOR DEBUGING PURPOSE ONLY!
        self.yaml = yaml
    
    
    def get_object_from_parameter_file(self, parameters_file_path, suffix=''):
        if not os.path.exists(parameters_file_path):
            logger.error('The parameters file %s is missing' % parameters_file_path)
            sys.exit(2)
        with open(parameters_file_path, 'r') as f:
            buf = f.read()
        # If we want to suffix the file, be sure to only add a line
        # and beware of the void file too
        if suffix:
            if buf:
                if buf.endswith('\n'):
                    buf += '%s\n' % suffix
                else:
                    buf += '\n%s\n' % suffix
            else:  # void file
                buf = '%s\n' % suffix
        
        # As we have a parameter style, need to insert dummy key entry to have all comments, even the first key one
        o = self.loads(buf, force_document_comment_to_first_entry=True)
        return o
    
    
    def set_value_in_parameter_file(self, parameters_file_path, parameter_name, python_value, str_value, change_type='SET'):
        o = yamler.get_object_from_parameter_file(parameters_file_path, suffix=ENDING_SUFFIX)
        
        # Set the value into the original object
        o[parameter_name] = python_value
        
        # Add a change history entry
        # BEWARE: only a oneliner!
        value_str = str_value.replace('\n', ' ')
        change_line = '# CHANGE: (%s) %s %s %s %s' % (datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'), change_type, parameter_name, CHARACTERS.arrow_left, value_str)
        yamler.add_document_ending_comment(o, change_line, ENDING_SUFFIX)
        
        result_str = yamler.dumps(o)
        tmp_file = '%s.tmp' % parameters_file_path
        f = open(tmp_file, 'w')
        f.write(result_str)
        f.close()
        shutil.move(tmp_file, parameters_file_path)
    
    
    def dumps(self, o):
        StringIO = libstore.get_StringIO()
        f = StringIO()
        yaml.round_trip_dump(o, f, default_flow_style=False)
        buf = f.getvalue()
        return buf
    
    
    # when loading, cal insert a key entry at start, for parameters, in order to allow
    # the first real key to have comments and not set in the global document one
    def loads(self, s, force_document_comment_to_first_entry=False):
        if force_document_comment_to_first_entry:
            s = '____useless_property: true\n' + s
        data = yaml.round_trip_load(s)
        if force_document_comment_to_first_entry:
            del data['____useless_property']
        return data
    
    
    def get_document_comment(self, data):
        if not isinstance(data, yaml.comments.CommentedMap):
            logger.error('Cannot access comment to document because it is not a CommentedMap object (%s)' % type(data))
            return None
        # something like this : [None, [CommentToken(value=u'# Document gull comment\n'), CommentToken(value=u'# document full comment bis\n')]]
        c = data.ca.comment
        return ''.join([ct.value for ct in c[1]]).strip()
    
    
    def get_document_ending_comment(self, data):
        if not isinstance(data, yaml.comments.CommentedMap):
            logger.error('Cannot access comment to document because it is not a CommentedMap object (%s)' % type(data))
            return None
        # something like this : [None, [CommentToken(value=u'# Document gull comment\n'), CommentToken(value=u'# document full comment bis\n')]]
        cts = data.ca.end
        if cts is None:
            return None
        return ''.join([ct.value for ct in cts]).strip()
    
    
    def get_key_comment(self, data, key):
        if not isinstance(data, yaml.comments.CommentedMap):
            logger.error('Cannot access comment to document because it is not a CommentedMap object (%s)' % type(data))
            return ''
        key_comments = data.ca.items
        
        # Maybe this key do not have comments
        if key not in key_comments:
            return None
        res = []
        # if have one, will be something like this
        # Key2 line before comment
        # key2: 36.000  # key2 same line comment
        # 'key2': [None, [CommentToken(value=u'# Key2 line before comment\n')], CommentToken(value=u'# key2 same line comment\n'), None]
        lines_before_cts = key_comments[key][1]
        if lines_before_cts is not None:
            res.extend([ct.value for ct in lines_before_cts])
        same_line_ct = key_comments[key][2]
        if same_line_ct:
            res.append(same_line_ct.value)
        
        return ''.join(res).strip()
    
    
    def add_document_ending_comment(self, doc, s, what_to_replace):
        if not isinstance(doc, yaml.comments.CommentedMap):
            logger.error('Cannot set comments to document because it is not a CommentedMap object (%s)' % type(doc))
            return
        ending_comments = doc.ca.end
        # TODO: how to CREATE comments from scratch?
        if ending_comments is None or ending_comments is []:
            logger.error('Cannot create new ending comment entry')
            return
        for ct in ending_comments:
            if what_to_replace in ct.value:
                ct.value = s
                return


yamler = YamlMgr()
