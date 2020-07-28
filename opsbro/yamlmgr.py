import os
import sys
import shutil
import datetime
import time
import codecs

from .characters import CHARACTERS
import opsbro.misc
from .library import libstore
from .log import LoggerFactory
from .util import bytes_to_unicode, PY3

ruamel_yaml = None

# One logger for the lib loading, an other for the yaml editing part
perf_logger = LoggerFactory.create_logger('performance')
logger = LoggerFactory.create_logger('yaml')


def get_ruamel_yaml():
    global ruamel_yaml
    perf_logger.debug('[yaml] Loading the ruamel yaml lib. it is slower than the simple yaml, but need for editing the configuration.')
    p = os.path.join(os.path.dirname(opsbro.misc.__file__), 'internalyaml')
    sys.path.insert(0, p)
    import ruamel.yaml as ruamel_yaml
    ruamel_yaml = ruamel_yaml
    return ruamel_yaml


simple_yaml = None
simple_yaml_loader = None


def get_simple_yaml():
    global simple_yaml, simple_yaml_loader
    # Always load simple yaml as we load the agent with it
    try:
        import yaml as simple_yaml
        from yaml import CLoader as simple_yaml_loader
    except ImportError:  # oups not founded, take the internal one
        perf_logger.debug('[yaml] Cannot import simple yaml lib. Switching to the full embedded ruamel lib instead. Will be slower.')
        simple_yaml = get_ruamel_yaml()
    return simple_yaml


ENDING_SUFFIX = '#___ENDING___'


# Class to wrap several things to json, like manage some utf8 things and such things
class YamlMgr(object):
    def __init__(self):
        # To allow some libs to directly call ruaml.yaml. FOR DEBUGING PURPOSE ONLY!
        self.ruamel_yaml = None
        self.simple_yaml = None
    
    
    def get_yaml_lib(self, with_comments=False):
        if with_comments:
            if self.ruamel_yaml is None:  # ok need to load the lib
                self.ruamel_yaml = get_ruamel_yaml()
            return self.ruamel_yaml
        # simple one
        if self.simple_yaml is None:
            self.simple_yaml = get_simple_yaml()
        return self.simple_yaml
    
    
    def get_object_from_parameter_file(self, parameters_file_path, suffix='', with_comments=False):
        if not os.path.exists(parameters_file_path):
            logger.error('The parameters file %s is missing' % parameters_file_path)
            sys.exit(2)
        with codecs.open(parameters_file_path, 'r', 'utf8') as f:
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
        o = self.loads(buf, force_document_comment_to_first_entry=True, with_comments=with_comments)
        return o
    
    
    def set_value_in_parameter_file(self, parameters_file_path, parameter_name, python_value, str_value, change_type='SET'):
        o = self.get_object_from_parameter_file(parameters_file_path, suffix=ENDING_SUFFIX, with_comments=True)
        
        # Set the value into the original object
        o[parameter_name] = python_value
        
        # Add a change history entry
        # BEWARE: only a oneliner!
        value_str = str_value.replace('\n', ' ')
        change_line = u'# CHANGE: (%s) %s %s %s %s' % (datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'), change_type, parameter_name, CHARACTERS.arrow_left, value_str)
        self.add_document_ending_comment(o, change_line, ENDING_SUFFIX)
        
        result_str = self.dumps(o)
        tmp_file = '%s.tmp' % parameters_file_path
        f = codecs.open(tmp_file, 'wb', 'utf8')
        # always save as unicode, because f.write() will launch an error if not
        s = bytes_to_unicode(result_str)
        f.write(s)
        f.close()
        shutil.move(tmp_file, parameters_file_path)
    
    
    def dumps(self, o):
        StringIO = libstore.get_StringIO()
        f = StringIO()
        yamllib = self.get_yaml_lib(with_comments=True)  # when writing, comments are mandatory
        yamllib.round_trip_dump(o, f, default_flow_style=False)
        buf = f.getvalue()
        return buf
    
    
    # when loading, cal insert a key entry at start, for parameters, in order to allow
    # the first real key to have comments and not set in the global document one
    def loads(self, s, force_document_comment_to_first_entry=False, with_comments=False):
        if not with_comments:  # don't care about first comment if we don't care about coments globaly
            force_document_comment_to_first_entry = False
        if force_document_comment_to_first_entry:
            s = '____useless_property: true\n' + s
        yamllib = self.get_yaml_lib(with_comments)
        if with_comments:
            data = yamllib.round_trip_load(s)
        else:
            # The yaml lib do not manage loads, so need to fake it first
            StringIO = libstore.get_StringIO_unicode_compatible()
            fake_file = StringIO(s)  # unicode_to_bytes(s))
            if simple_yaml_loader is not None:
                data = yamllib.load(fake_file, Loader=simple_yaml_loader)
            else:  # ruamel
                data = yamllib.round_trip_load(s)
        if force_document_comment_to_first_entry:
            del data['____useless_property']
        return data
    
    
    def get_document_comment(self, data):
        yamllib = self.get_yaml_lib(with_comments=True)
        if not isinstance(data, yamllib.comments.CommentedMap):
            logger.error('Cannot access comment to document because it is not a CommentedMap object (%s)' % type(data))
            return None
        # something like this : [None, [CommentToken(value=u'# Document gull comment\n'), CommentToken(value=u'# document full comment bis\n')]]
        c = data.ca.comment
        return ''.join([ct.value for ct in c[1]]).strip()
    
    
    def get_document_ending_comment(self, data):
        yamllib = self.get_yaml_lib(with_comments=True)
        if not isinstance(data, yamllib.comments.CommentedMap):
            logger.error('Cannot access comment to document because it is not a CommentedMap object (%s)' % type(data))
            return None
        # something like this : [None, [CommentToken(value=u'# Document gull comment\n'), CommentToken(value=u'# document full comment bis\n')]]
        cts = data.ca.end
        if cts is None:
            return None
        return ''.join([ct.value for ct in cts]).strip()
    
    
    def get_key_comment(self, data, key):
        yamllib = self.get_yaml_lib(with_comments=True)
        if not isinstance(data, yamllib.comments.CommentedMap):
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
        yamllib = self.get_yaml_lib(with_comments=True)
        if not isinstance(doc, yamllib.comments.CommentedMap):
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
