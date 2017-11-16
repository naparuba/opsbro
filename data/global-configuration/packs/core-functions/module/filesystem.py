import os
import re

from opsbro.evaluater import export_evaluater_function
from opsbro.log import logger

FUNCTION_GROUP = 'filesystem'


@export_evaluater_function(function_group=FUNCTION_GROUP)
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


@export_evaluater_function(function_group=FUNCTION_GROUP)
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


@export_evaluater_function(function_group=FUNCTION_GROUP)
def path_dirname(path):
    """**path_dirname(path)** -> Return the parent directory name for given path.

 * path: (string) path of the file to look inside.

<code>
    Example:
        path_dirname('/etc/apache2/httpd.conf')
    Returns:
        '/etc/apache2'
</code>
    """
    return os.path.dirname(path)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def is_dir(path):
    """**is_dir(path)** -> Return True if the path is a directory, False overwise

 * path: (string) path of the path to check.

<code>
    Example:
        is_dir('/etc/apache2/')
    Returns:
        True
</code>
    """
    return os.path.isdir(path)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def is_link(path):
    """**is_link(path)** -> Return True if the path is a symbolic link, False overwise

 * path: (string) path of the path to check.

<code>
    Example:
        is_link('/etc/apache2/http.conf')
    Returns:
        False
</code>
    """
    return os.path.islink(path)


'''
accessedbefore
Table of Contents
Prototype: accessedbefore(newer, older)
Return type: boolean
Description: Compares the atime fields of two files.
Return true if newer was accessed before older.
Arguments:
newer: string, in the range: "?(/.*)
older: string, in the range: "?(/.*)
Example:
Prepare:
touch -a -t '200102031234.56' /tmp/earlier
touch -a -t '200202031234.56' /tmp/later
Run:
body common control
{
      bundlesequence  => { "example" };
}

bundle agent example
{
  classes:
      "do_it" expression => accessedbefore("/tmp/earlier","/tmp/later");

  reports:
    do_it::
      "The secret changes have been accessed after the reference time";
}
Output:
R: The secret changes have been accessed after the reference time
See Also: changedbefore(), isnewerthan()
'''

'''
changedbefore
Table of Contents
Prototype: changedbefore(newer, older)
Return type: boolean
Description: Compares the ctime fields of two files.
Returns true if newer was changed before older, otherwise returns false.
Change times include both file permissions and file contents. Comparisons like this are normally used for updating files (like the 'make' command).
Arguments:
newer: string, in the range: "?(/.*)
older: string, in the range: "?(/.*)
Example:
    body common control
    {
      bundlesequence  => { "example" };
    }

    bundle agent example
    {
      classes:

        "do_it" and => { changedbefore("/tmp/earlier","/tmp/later"), "linux" };

      reports:

        do_it::

          "The derived file needs updating";
    }
See Also: accessedbefore(), isnewerthan()
'''

'''
countlinesmatching
Table of Contents
Prototype: countlinesmatching(regex, filename)
Return type: int
Description: Count the number of lines in file filename matching regex.
This function matches lines in the named file, using an anchored regular expression that should match the whole line, and returns the number of lines matched.
Arguments:
regex: regular expression, in the range: .*
filename: string, in the range: "?(/.*)
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      # typically there is only one root user
      "no" int => countlinesmatching("root:.*","/etc/passwd");

  reports:
      "Found $(no) lines matching";
}
Output:
R: Found 1 lines matching
'''

'''
filestat
Table of Contents
Prototype: filestat(filename, field)
Return type: string
Description: Returns the requested file field field for the file object filename.
If the file object does not exist, the function call fails and the variable does not expand.
Arguments:
filename : the file or directory name to inspect, in the range: "?(/.*)
field : the requested field, with the following allowed values:
size : size in bytes
gid : group ID
uid : owner ID
ino : inode number
nlink : number of hard links
ctime : creation time in Unix epoch format
atime : last access time in Unix epoch format
mtime : last modification time in Unix epoch format
mode : file mode as a decimal number
modeoct : file mode as an octal number, e.g. 10777
permstr : permission string, e.g. -rwx---rwx (not available on Windows)
permoct : permissions as an octal number, e.g. 644 (not available on Windows)
type : file type (not available on Windows): block device,character device, directory, FIFO/pipe, symlink, regular file, socket, or unknown
devno : device number (drive letter on Windows, e.g. C:)
dev_minor : minor device number (not available on Windows)
dev_major : major device number (not available on Windows)
basename : the file name minus the directory
dirname : the directory portion of the file name
linktarget : if the file is a symlink, its final target. The target is chased up to 32 levels of recursion. On Windows, this returns the file name itself.
linktarget_shallow : if the file is a symlink, its first target. On Windows, this returns the file name itself.
xattr : a string with newline-separated extended attributes and SELinux contexts in key=value<NEWLINE>key2=value2<NEWLINE>tag1<NEWLINE>tag2 format.
On Mac OS X, you can list and set extended attributes with the xattr utility.
On SELinux, the contexts are the same as what you see with ls -Z.
Example:
Prepare:
echo 1234567890 > FILE.txt
chmod 0755 FILE.txt
chown 0 FILE.txt
chgrp 0 FILE.txt
Run:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "file" string => "$(this.promise_filename).txt";
  methods:
      "fileinfo" usebundle => fileinfo("$(file)");
}
bundle agent fileinfo(f)
{
  vars:
      # use the full list if you want to see all the attributes!
      # "fields" slist => splitstring("size,gid,uid,ino,nlink,ctime,atime,mtime,mode,modeoct,permstr,permoct,type,devno,dev_minor,dev_major,basename,dirname,linktarget,linktarget_shallow", ",", 999);

      # ino (inode number), ctime (creation time),
      # devno/dev_minor/dev_major (device numbers) were omitted but
      # they are all integers

      "fields" slist => splitstring("size,gid,uid,nlink,mode,modeoct,permstr,permoct,type,basename", ",", 999);

      "stat[$(f)][$(fields)]" string => filestat($(f), $(fields));

  reports:
      "$(this.bundle): file $(stat[$(f)][basename]) has $(fields) = $(stat[$(f)][$(fields)])";
}
Output:
R: fileinfo: file filestat.cf.txt has size = 11
R: fileinfo: file filestat.cf.txt has gid = 0
R: fileinfo: file filestat.cf.txt has uid = 0
R: fileinfo: file filestat.cf.txt has nlink = 1
R: fileinfo: file filestat.cf.txt has mode = 33261
R: fileinfo: file filestat.cf.txt has modeoct = 100755
R: fileinfo: file filestat.cf.txt has permstr = -rwxr-xr-x
R: fileinfo: file filestat.cf.txt has permoct = 755
R: fileinfo: file filestat.cf.txt has type = regular file
R: fileinfo: file filestat.cf.txt has basename = filestat.cf.txt
Notes:
linktarget will prepend the directory name to relative symlink targets, in order to be able to resolve them. Use linktarget_shallow to get the exact link as-is in case it is a relative link.
The list of fields may be extended as needed by CFEngine.
History: Was introduced in version 3.5.0,Enterprise 3.1 (2013). linktarget and linktarget_shallow were added in version 3.6.
'''

'''
findfiles
Table of Contents
Prototype: findfiles(glob1, glob2, ...)
Return type: slist
Description: Return the list of files that match any of the given glob patterns.
This function searches for the given glob patterns in the local filesystem, returning files or directories that match. Note that glob patterns are not regular expressions. They match like Unix shells:
* matches any filename or directory at one level, e.g. *.cf will match all files in one directory that end in .cf but it won't search across directories. */*.cf on the other hand will look two levels deep.
? matches a single letter
[a-z] matches any letter from a to z
{x,y,anything} will match x or y or anything.
This function, used together with the bundlesmatching function, allows you to do dynamic inputs and a dynamic bundle call chain.
Example:
body common control
{
      bundlesequence => { run };
}

bundle agent run
{
  vars:
      "findtmp" slist => findfiles("/[tT][mM][pP]");
      # or find all .txt files under /tmp, up to 6 levels deep...
      # "findtmp" slist => findfiles("/tmp/**/*.txt");
  reports:
      "All files that match '/[tT][mM][pP]' = $(findtmp)";
}
Output:
R: All files that match '/[tT][mM][pP]' = /tmp
See also: bundlesmatching().
'''

'''
filesize
Table of Contents
Prototype: filesize(filename)
Return type: int
Description: Returns the size of the file filename in bytes.
If the file object does not exist, the function call fails and the variable does not expand.
Arguments:
filename: string, in the range: "?(/.*)
Example:
Run:
body common control
{
      bundlesequence => { example };
}

bundle agent example
{
  vars:
      # my own size!
      "exists" int => filesize("$(this.promise_filename)");
      "nexists" int => filesize("/etc/passwdx");

  reports:
      "File size $(exists)";
      "Does not exist: $(nexists)";
}
Output:
R: File size 301
R: Does not exist: $(nexists)
History: Was introduced in version 3.1.3, Nova 2.0.2 (2010).
'''

'''
getfields
Table of Contents
Prototype: getfields(regex, filename, split, array_lval)
Return type: int
Description: Fill array_lval with fields in the lines from file filename that match regex, split on split.
The function returns the number of lines matched. This function is most useful when you want only the first matching line (e.g., to mimic the behavior of the getpwnam(3) on the file /etc/passwd). If you want to examine all lines, use readstringarray() instead.
Arguments:
regex : Regular expression to match line, in the range .*
A regular expression matching one or more lines. The regular expression is anchored, meaning it must match the entire line.
filename : Filename to read, in the range "?(/.*)
The name of the file to be examined.
split : Regular expression to split fields, in the range .*
A regex pattern that is used to parse the field separator(s) to split up the file into items
array_lval : Return array name, in the range .*
The base name of the array that returns the values.
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:

      "no" int => getfields("root:.*","/etc/passwd",":","userdata");

  reports:
      "Found $(no) lines matching";
      "root's handle = $(userdata[1])";
      "root's passwd = ... forget it!";
      "root's uid = $(userdata[3])";
      # uncomment this if you want to see the HOMEDIR field
      #"root's homedir = $(userdata[6])";
      # uncomment this if you want to see the GID field
      #"root's gid = $(userdata[4])";
      # uncomment this if you want to see the GECOS field
      #"root's name = $(userdata[5])";

}
Output:
R: Found 1 lines matching
R: root's handle = root
R: root's passwd = ... forget it!
R: root's uid = 0
Notes: This function matches lines (using a regular expression) in the named file, and splits the first matched line into fields (using a second regular expression), placing these into a named array whose elements are array[1],array[2],... This is useful for examining user data in the Unix password or group files.
'''

'''
isexecutable
Table of Contents
Prototype: isexecutable(filename)
Return type: boolean
Description: Returns whether the named object filename has execution rights for the current user.
Arguments:
filename: string, in the range: "?(/.*)
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  classes:

      "yes" expression => isexecutable("/bin/ls");
  reports:
    yes::
      "/bin/ls is an executable file";
}
Output:
R: /bin/ls is an executable file
History: Was introduced in version 3.1.0b1,Nova 2.0.0b1 (2010)
'''

'''
isnewerthan
Table of Contents
Prototype: isnewerthan(newer, older)
Return type: boolean
Description: Returns whether the file newer is newer (modified later) than the file older.
This function compares the modification time (mtime) of the files, referring to changes of content only.
Arguments:
newer: string, in the range: "?(/.*)
older: string, in the range: "?(/.*)
Example:
Prepare:
touch -t '200102031234.56' /tmp/earlier
touch -t '200202031234.56' /tmp/later
Run:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  classes:

      "do_it" and => { isnewerthan("/tmp/later","/tmp/earlier"), "cfengine" };

  reports:

    do_it::

      "/tmp/later is older than /tmp/earlier";
}
Output:
R: /tmp/later is older than /tmp/earlier
See Also: accessedbefore(), changedbefore()
'''

'''
lsdir
Table of Contents
Prototype: lsdir(path, regex, include_base)
Return type: slist
Description: Returns a list of files in the directory path matching the regular expression regex.
If include_base is true, full paths are returned, otherwise only names relative to the directory are returned.
Arguments:
path: string, in the range: .+
regex: regular expression, in the range: .*
include_base: one of
true
false
yes
no
on
off
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "listfiles" slist => lsdir("/etc", "(p.sswd|gr[ou]+p)", "true");
      "sorted_listfiles" slist => sort(listfiles, "lex");

  reports:
      "files in list: $(sorted_listfiles)";
}
Output:
R: files in list: /etc/group
R: files in list: /etc/passwd
Notes:
History: Was introduced in 3.3.0, Nova 2.2.0 (2011)
'''
