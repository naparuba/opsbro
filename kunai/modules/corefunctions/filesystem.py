import os
import re

from kunai.evaluater import export_evaluater_function
from kunai.log import logger


@export_evaluater_function
def file_exists(path):
    """**file_exists(path)** -> return True if a path exist on the system, False otherwise.

 * path: (string) path to check.

<code>
    Example:

        file_exists('/etc/mongodb.conf')

    Returns:

        True

</code>

    """
    return os.path.exists(path)


@export_evaluater_function
def grep_file(string, path, regexp=False):
    """**file_exists(path)** -> return True if a string or a regexp match the content of a file, False otherwise.

 * string: (string)  string (or regexp expression) to check
 * path: (string) path of the file to look inside.
 * regexp: (boolean) is the string a regexp or not.

<code>
    Example:
        grep_file('centos', '/etc/redhat-release')
    Returns:
        True
</code>
    """
    s = string
    p = path
    if not os.path.exists(p):
        logger.debug('[evaluater::grep_file] no such fle %s' % p)
        return False
    try:
        f = open(p, 'r')
        lines = f.readlines()
    except Exception, exp:
        logger.error('[evaluater::grep_file] Trying to grep file %s but cannot open/read it: %s' % (p, exp))
        return False
    pat = None
    if regexp:
        try:
            pat = re.compile(s, re.I)
        except Exception, exp:
            logger.error('[evaluater::grep_file]Cannot compile regexp expression: %s')
        return False
    if regexp:
        for line in lines:
            if pat.search(line):
                return True
    else:
        s = s.lower()
        for line in lines:
            if s in line.lower():
                return True
    logger.debug('[evaluater::grep_file] GREP FILE FAIL: no such line %s %s' % (p, s))
    return False
