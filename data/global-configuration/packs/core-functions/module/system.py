import os
import codecs

from opsbro.evaluater import export_evaluater_function
from opsbro.misc.lolcat import lolcat
from opsbro.util import PY3
from opsbro.jsonmgr import jsoner

if PY3:
    basestring = str

FUNCTION_GROUP = 'system'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_get_os():
    """**system_get_os()** -> return a string about the os.

<code>
    Example:
        system_get_os()

    Returns:
        'linux'
</code>
    """
    import platform
    return platform.system().lower()


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_is_python_2():
    """**system_is_python_2()** -> return True if the agent is running on python2, False otherwise

<code>
    Example:
        system_is_python_2()

    Returns:
        True
</code>
    """
    return not PY3


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_is_python_3():
    """**system_is_python_3()** -> return True if the agent is running on python3, False otherwise

<code>
    Example:
        system_is_python_3()

    Returns:
        False
</code>
    """
    return PY3


#################### USERS
try:
    import pwd, grp
    from pwd import getpwnam
    from grp import getgrnam
except ImportError as exp:
    getpwnam = getgrnam = None


def _uname_to_uid(uname):
    try:
        return getpwnam(uname)
    except KeyError:  # no such group sorry
        return None


def _uid_to_uname(uid):
    try:
        return pwd.getpwuid(uid)
    except KeyError:  # no such group sorry
        return None


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_user_exists(username_or_uid):
    """**system_user_exists(uname_or_uid)** -> return True if the node username/uid does exists, False otherwise.

 * username_or_uid: (string or int) string of the username or int for the user id.

<code>
    Example:
        system_user_exists('root')
    Returns:
        True
</code>
    """
    if getpwnam is None:
        raise Exception('This function is not available on this OS')
    
    # is an int or a string?
    try:
        uid = int(username_or_uid)
    except ValueError:
        uid = None
    
    # Maybe we have a uid, maybe a string to search
    if uid is not None:
        r = _uid_to_uname(uid)
        return r is not None
    r = _uname_to_uid(username_or_uid)
    return r is not None


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_userid_from_username(username):
    """**system_userid_from_username(username)** -> return userid that match the username, None overwise.

 * username: (string) name of the user to search

<code>
    Example:
        system_userid_from_username('root')
    Returns:
        0
</code>
    """
    if getpwnam is None:
        raise Exception('This function is not available on this OS')
    
    return _uname_to_uid(username)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_username_from_userid(userid):
    """**system_username_from_userid(userid)** -> return userid that match the username, None overwise.

 * userid: (integer) id of the user to give

<code>
    Example:
        system_username_from_userid(0)
    Returns:
        'root'
</code>
    """
    if getpwnam is None:
        raise Exception('This function is not available on this OS')
    
    return _uid_to_uname(userid)


#################### GROUPS

def _gname_to_gid(gname):
    try:
        return getgrnam(gname)
    except KeyError:  # no such group sorry
        return None


def _gid_to_gname(gid):
    try:
        return grp.getgrgid(gid)
    except KeyError:  # no such group sorry
        return None


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_group_exists(groupname_or_gid):
    """**group_exists(groupname_or_gid)** -> return True if the groupname/gid does exists, False otherwise.

 * groupname_or_gid: (string or int) string of the groupname or int for the group id.

<code>
    Example:
        group_exists('www-data')
    Returns:
        True
</code>
    """
    if getgrnam is None:
        raise Exception('This function is not available on this OS')
    
    # is an int or a string?
    try:
        gid = int(groupname_or_gid)
    except ValueError:
        gid = None
    
    # Maybe we have a uid, maybe a string to search
    if gid is not None:
        r = _gid_to_gname(gid)
        return r is not None
    # else: is a string
    r = _gname_to_gid(groupname_or_gid)
    return r is not None


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_groupid_from_groupname(groupname):
    """**system_groupid_from_groupname(groupname)** -> return groupid that match the groupname, None overwise.

 * groupname: (string) name of the group to search

<code>
    Example:
        system_groupid_from_groupname('root')
    Returns:
        0
</code>
    """
    if getgrnam is None:
        raise Exception('This function is not available on this OS')
    
    return _gname_to_gid(groupname)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def system_groupname_from_groupid(groupid):
    """**system_groupname_from_groupid(groupid)** -> return groupname that match the groupid, None overwise.

 * groupid: (integer) id of the group to give

<code>
    Example:
        system_groupname_from_groupid(0)
    Returns:
        'root'
</code>
    """
    if getgrnam is None:
        raise Exception('This function is not available on this OS')
    
    return _gid_to_gname(groupid)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def colorize(s, color):
    """**colorize(s, color)** -> return the string s with the color (ainsi)

 * s: (string) string to colorize
 * color: (int between 1 -> 64) ainsi color

<code>
    Example:
        colorize('my string', 55)
    Returns:
        \x1b[55Dmy string\x1b[0m
</code>
    """
    if not isinstance(s, basestring):
        try:
            s = unicode(s)
        except:
            return ''
    return lolcat.get_line(s, color, spread=None)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def is_plain_file(path):
    """**is_plain_file(path)** -> return True if the file at path is a plain file

 * path: (string) path to check

<code>
    Example:
        is_plain_file('/etc/passwd')
    Returns:
        True
</code>
    """
    return os.path.isfile(path)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def parse_json_file(path):
    """**parse_json_file(path)** -> return the object read from the file at path

 * path: (string) path of the json file to parse

<code>
    Example:
        parse_json_file('/tmp/my_file.json')
    Returns:
        {'key':'value'}
</code>
    """
    with codecs.open(path, 'r', 'utf8') as f:
        o = jsoner.loads(f.read())
    return o


@export_evaluater_function(function_group=FUNCTION_GROUP)
def get_env(variable):
    """**get_env(variable)** -> return the value of the environnement variable

 * variable: (string) name of the variable to ask

<code>
    Example:
        get_env('LANG')
    Returns:
        'en_US.UTF-8'
</code>
    """
    return os.environ.get(variable, '')


'''
findprocesses
Table of Contents
Prototype: findprocesses(regex)
Return type: data
The return value is cached.
Description: Return the list of processes that match the given regular expression regex.
This function searches for the given regular expression in the process table. Use .*sherlock.* to find all the processes that match sherlock. Use .*\bsherlock\b.* to exclude partial matches like sherlock123 (\b matches a word boundary).
Arguments:
regex: regular expression, in the range: .*
The returned data container is a list of key-value maps. Each one is guaranteed to have the key pid with the process ID. The key line will also be available with the raw process table contents.
The process table is usually obtained with something like ps -eo user,pid,ppid,pgid,%cpu,%mem,vsize,ni,rss,stat,nlwp,stime,time,args, and the CMD or COMMAND field (args) is used to match against. However the exact data used may change per platform and per CFEngine release.
Example:
    vars:
      "holmes" data => findprocesses(".*sherlock.*");
Output:
    [ { "pid": "2378", "line": "...the ps output here" }, ... ]
History: Introduced in CFEngine 3.9
See also: processes processexists().
'''

'''
getusers
Table of Contents
Prototype: getusers(exclude_names, exclude_ids)
Return type: slist
Description: Returns a list of all users defined, except those names in exclude_names and uids in exclude_ids
Arguments:
exclude_names: string, in the range: .*
exclude_ids: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "allusers" slist => getusers("","");
      "root_list" slist => { "root" };
      # this will get just the root users out of the full user list
      "justroot" slist => intersection(allusers, root_list);

  reports:
      "Found just the root user: $(justroot)";
}
Output:
R: Found just the root user: root
Notes: This function is currently only available on Unix-like systems.
History: Was introduced in version 3.1.0b1,Nova 2.0.0b1 (2010).
See also: getuserinfo(), users.
'''

'''
getuserinfo
Table of Contents
Prototype: getuserinfo(optional_uidorname)
Return type: data
Description: Return information about the current user or any other, looked up by user ID (UID) or user name.
This function searches for a user known to the system. If the optional_uidorname parameter is omitted, the current user (that is currently running the agent) is retrieved. If optional_uidorname is specified, the user entry is looked up by name or ID, using the standard getpwuid() and getpwnam() POSIX functions (but note that these functions may in turn talk to LDAP, for instance).
On platforms that don't support these POSIX functions, the function simply fails.
Arguments:
optional_uidorname: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
    vars:
      # note the results here will vary depending on your platform
      "me" data => getuserinfo(); # the current user's info
      "root" data => getuserinfo("root"); # the "root" user's info (usually UID 0)
      "uid0" data => getuserinfo(0); # lookup user info for UID 0 (usually "root")

      # sys.user_data has the information for the user that started the agent
      "out" string => format("I am '%s', root shell is '%s', and the agent was started by %S", "$(me[description])", "$(root[shell])", "sys.user_data");

  reports:
      "$(out)";
}
Typical Results:
R: I am 'Mr. Current User', root shell is '/bin/bash', and the agent was started by {"description":"Mr. Current User","gid":1000,"home_dir":"/home/theuser","shell":"/bin/sh","uid":1000,"username":"theuser"}

And variable contents:
  "me": {
    "description": "Mr. Current User",
    "gid": 1000,
    "home_dir": "/home/theuser",
    "shell": "/bin/sh",
    "uid": 1000,
    "username": "theuser"
  }

  "root": {
    "description": "root",
    "gid": 0,
    "home_dir": "/root",
    "shell": "/bin/bash",
    "uid": 0,
    "username": "root"
  }

  "uid0": {
    "description": "root",
    "gid": 0,
    "home_dir": "/root",
    "shell": "/bin/bash",
    "uid": 0,
    "username": "root"
  }
History: Introduced in CFEngine 3.10
See also: getusers(), users.
'''

'''
packagesmatching
Table of Contents
Prototype: packagesmatching(package_regex, version_regex, arch_regex, method_regex)
Return type: data
Description: Return a data container with the list of installed packages matching the parameters.
This function searches for the anchored regular expressions in the list of currently installed packages.
The return is a data container with a list of package descriptions, looking like this:
[
   {
      "arch":"default",
      "method":"dpkg",
      "name":"zsh-common",
      "version":"5.0.7-5ubuntu1"
   }
]
Arguments:
package_regex: string, in the range: .*
version_regex: string, in the range: .*
arch_regex: string, in the range: .*
method_regex: string, in the range: .*
Argument Descriptions:
package_regex - Regular expression matching packge name
version_regex - Regular expression matching package version
arch_regex - Regular expression matching package architecutre
method_regex - Regular expression matching package method (apt-get, rpm, etc ...)
The following code extracts just the package names, then looks for some desired packages, and finally reports if they are installed.
IMPORTANT: Please note that you need to provide package_inventory attribute in body common control in order to be able to use this function. Also depending on the value(s) of package_inventory only packages from selected package modules will be returned. For more information about package_inventory please read package_inventory section.
body common control

{
      bundlesequence => { "missing_packages" };
}


bundle agent missing_packages
{
  vars:
    # List of desired packages
    "desired" slist => { "mypackage1", "mypackage2" };

    # Get info on all installed packages
    "installed" data => packagesmatching(".*",".*",".*",".*");
    "installed_indices" slist => getindices(installed);

    # Build a simple array of the package names so that we can use
    # getvalues to pull a unified list of package names that are installed.
    "installed_name[$(installed_indices)]"
      string => "$(installed[$(installed_indices)][name])";

    # Get unified list of installed packages
    "installed_names" slist => getvalues("installed_name");

    # Determine packages that are missing my differencing the list of
    # desired packages, against the list of installed packages
    "missing_list" slist => difference(desired,installed_names);

  reports:
    # Report on packages that are missing, installed
    # and what we were looking for
    "Missing packages = $(missing_list)";
    "Installed packages = $(installed_names)";
    "Desired packages = $(desired)";
}
This policy can be found in /var/cfengine/share/doc/examples/packagesmatching.cf and downloaded directly from github.
Example:
      "all_packages" data => packagesmatching(".*", ".*", ".*", ".*");
Refresh rules: * inastalled packages cache used by packagesmatching() is refreshed at the end of each agent run in accordance with constraints defined in the relevant package module body. * installed packages cache is refreshed after installing or removing a package. * installed packages cache is refreshed if no local cache exists. This means a reliable way to force a refresh of CFEngine's internal package cache is to simply delete the local cache:
            $(sys.statedir)/packages_installed_<package_module>.lmdb*
History: Introduced in CFEngine 3.6
See also: packageupdatesmatching().
'''

'''
processexists
Table of Contents
Prototype: processexists(regex)
Return type: boolean
The return value is cached.
Description: Return whether a process matches the given regular expression regex.
This function searches for the given regular expression in the process table. Use .*sherlock.* to find all the processes that match sherlock. Use .*\bsherlock\b.* to exclude partial matches like sherlock123 (\b matches a word boundary).
Arguments:
regex: regular expression, in the range: .*
The process table is usually obtained with something like ps -eo user,pid,ppid,pgid,%cpu,%mem,vsize,ni,rss,stat,nlwp,stime,time,args, and the CMD or COMMAND field (args) is used to match against. However the exact data used may change per platform and per CFEngine release.
Example:
    classes:
      # the class "holmes" will be set if a process line contains the word "sherlock"
      "holmes" expression => processexists(".*sherlock.*");
History: Introduced in CFEngine 3.9
See also: processes findprocesses().
'''

'''
registryvalue
Table of Contents
Prototype: registryvalue(key, valueid)
Return type: string
Description: Returns the value of valueid in the Windows registry key key.
This function applies only to Windows-based systems. The value is parsed as a string.
Arguments:
key: string, in the range: .*
valueid: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "reg" };
}

bundle agent reg
{
  vars:
    windows::
      "value" string => registryvalue("HKEY_LOCAL_MACHINE\SOFTWARE\CFEngine AS\CFEngine","value3");
    !windows::
      "value" string => "Sorry, no registry data is available";

  reports:
      "Value extracted: $(value)";

}
Output:
R: Value extracted: Sorry, no registry data is available
Notes: Currently values of type REG_SZ (string), REG_EXPAND_SZ (expandable string) and REG_DWORD (double word) are supported.
'''

'''
readcsv
Table of Contents
Description: Parses CSV data from the first 1 MB of file filename and returns the result as a data variable.
While it may seem similar to data_readstringarrayidx() and data_readstringarray(), the readcsv() function is more capable because it follows RFC 4180, especially regarding quoting. This is not possible if you just split strings on a regular expression delimiter.
The returned data is in the same format as data_readstringarrayidx(), that is, a data container that holds a JSON array of JSON arrays.
Example:
Prepare:
echo -n 1,2,3 > /tmp/csv
Run:
bundle agent main
{
  vars:

      # note that the CSV file has to have ^M (DOS) EOL terminators
      # thus the prep step uses `echo -n` and just one line, so it will work on Unix
      "csv" data => readcsv("/tmp/csv");
      "csv_str" string => format("%S", csv);

  reports:

      "From /tmp/csv, got data $(csv_str)";

}
Output:
R: From /tmp/csv, got data [["1","2","3"]]
Note: CSV files formatted according to RFC 4180 must end with the CRLF sequence. Thus a text file created on Unix with standard Unix tools like vi will not, by default, have those line endings.
See also: readdata(), data_readstringarrayidx(),data_readstringarray(), parsejson(), storejson(), mergedata(), and data documentation.
History: Was introduced in 3.7.0.
'''
