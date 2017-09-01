from opsbro.evaluater import export_evaluater_function
from opsbro.gossip import gossiper


@export_evaluater_function
def get_os():
    """**get_os()** -> return a string about the os.

<code>
    Example:
        get_os()

    Returns:
        'linux'
</code>
    """
    import platform
    return platform.system().lower()


@export_evaluater_function
def have_group(group):
    """**have_group(group)** -> return True if the node have the group, False otherwise.

 * group: (string) group to check.


<code>
    Example:
        have_group('linux')
    Returns:
        True
</code>
    """
    return gossiper.have_group(group)




try:
    import pwd, grp
    from pwd import getpwnam
    from grp import getgrnam
except ImportError, exp:
    getpwnam = getgrnam = None


@export_evaluater_function
def user_exists(username_or_uid):
    """**user_exists(uname_or_uid)** -> return True if the node username/uid does exists, False otherwise.

 * username_or_uid: (string or int) string of the username or int for the user id.

<code>
    Example:
        user_exists('root')
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
        try:
            pwd.getpwuid(uid)
            # We can get it's data, he/she does exists
            return True
        except KeyError:
            # ok no such uid
            return False
    # else: is a string
    try:
        getpwnam(username_or_uid)
        return True  # we can get he/she data
    except KeyError:  # no such user sorry
        return False


@export_evaluater_function
def group_exists(groupname_or_gid):
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
        try:
            grp.getgrgid(gid)
            # We can get it's data, he/she does exists
            return True
        except KeyError:
            # ok no such uid
            return False
    # else: is a string
    try:
        getgrnam(groupname_or_gid)
        return True  # we can get he/she data
    except KeyError:  # no such group sorry
        return False

