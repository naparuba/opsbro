import os
import sys
from cStringIO import StringIO
import opsbro.misc

p = os.path.join(os.path.dirname(opsbro.misc.__file__), 'internalyaml')
sys.path.insert(0, p)

import ruamel.yaml as yaml

from opsbro.log import LoggerFactory

logger = LoggerFactory.create_logger('yaml')


# Class to wrap several things to json, like manage some utf8 things and such things
class YamlMgr(object):
    def __init__(self):
        pass
    
    
    def dumps(self, o):
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


yamler = YamlMgr()
