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


@export_evaluater_function(function_group=FUNCTION_GROUP)
def is_in_defined_group(group):
    """**is_in_defined_group(group)** -> return True if the node have the group but was set in the configuration, not from discovery False otherwise.

 * group: (string) group to check.


<code>
    Example:
        is_in_defined_group('linux')
    Returns:
        True
</code>
    """
    return gossiper.is_in_group(group)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def gossip_get_zone(node_uuid=''):
    """**gossip_get_zone(node_uuid='')** -> return the zone (as string) of the node with the uuid node_uuid. If uset, get the current node.

 * node_uuid: (string) uuid of the element to get zone.


<code>
    Example:
        gossip_get_zone()
    Returns:
        'internet'
</code>
    """
    return gossiper.get_zone_from_node(node_uuid)
