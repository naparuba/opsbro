from opsbro.evaluater import export_evaluater_function
from opsbro.hostingcontextmanager import get_hostingcontextmgr

FUNCTION_GROUP = 'hosting'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def hosting_context_is_active(context_name):
    """**hosting_context_is_active(context_name)** -> return True if this hosting context is active.

<code>
    Example:
        hosting_context_is_active('ec2')

    Returns:
        True
</code>
    """
    
    hostingctxmgr = get_hostingcontextmgr()
    return hostingctxmgr.is_context_active(context_name)
