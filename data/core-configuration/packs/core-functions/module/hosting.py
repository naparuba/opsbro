from opsbro.evaluater import export_evaluater_function
from opsbro.hostingdrivermanager import get_hostingdrivermgr

FUNCTION_GROUP = 'hosting'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def hosting_driver_is_active(driver_name):
    """**hosting_driver_is_active(driver_name)** -> return True if this hosting driver is active.

<code>
    Example:
        hosting_driver_is_active('ec2')

    Returns:
        True
</code>
    """
    
    hostingctxmgr = get_hostingdrivermgr()
    return hostingctxmgr.is_driver_active(driver_name)
