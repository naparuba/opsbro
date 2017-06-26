from kunai.evaluater import export_evaluater_function
from kunai.gossip import gossiper


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
def have_tag(tag):
    """**have_tag(tag)** -> return True if the node have the tag, False otherwise.

 * tag: (string) tag to check.


<code>
    Example:
        have_tag('linux')
    Returns:
        True
</code>
    """
    return gossiper.have_tag(tag)
