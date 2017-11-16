from opsbro.evaluater import export_evaluater_function
from opsbro.gossip import gossiper

FUNCTION_GROUP = 'gossip'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def is_in_group(group):
    """**is_in_group(group)** -> return True if the node have the group, False otherwise.

 * group: (string) group to check.


<code>
    Example:
        is_in_group('linux')
    Returns:
        True
</code>
    """
    return gossiper.is_in_group(group)
