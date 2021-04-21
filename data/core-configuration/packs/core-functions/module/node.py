from collections import deque

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
def is_in_static_group(group):
    """**is_in_static_group(group)** -> return True if the node have the group but was set in the configuration, not from discovery False otherwise.

 * group: (string) group to check.


<code>
    Example:
        is_in_static_group('linux')
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


@export_evaluater_function(function_group=FUNCTION_GROUP)
def gossip_count_nodes(group='', state=''):
    """**gossip_count_nodes(group='', state='')** -> return the number of known nodes that match group and state

 * group: (string) if set, count only the members of this group.
 * state: (string) if set, count only the members with this state.


<code>
    Example:
        gossip_count_nodes(group='linux', state='ALIVE')
    Returns:
        3
</code>
    """
    return gossiper.count(group=group, state=state)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def gossip_have_event_type(event_type):
    """**gossip_have_event(event_type)** -> return True if an event of event_type is present in the node

 * event_type: (string) type of event to detect.


<code>
    Example:
        gossip_have_event_type('shinken-restart')
    Returns:
        False
</code>
    """
    return gossiper.have_event_type(event_type)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def compliance_get_state_of_rule(rule_name):
    """**compliance_get_state_of_rule(rule_name)** -> return the state of the rule with the name rule_name

 * rule_name: (string) name of the rule to get. If wrong, state will be UNKNOWN.


<code>
    Example:
        compliance_get_state_of_rule('Install mongodb')
    Returns:
        'COMPLIANT'
</code>
    """
    from opsbro.compliancemgr import compliancemgr
    return compliancemgr.get_rule_state(rule_name)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def get_other_node_address(other_node_name_or_uuid):
    """**get_other_node_address(other_node_name_or_uuid)** -> return as string the address of the other node

 * other_node_name_or_uuid: (string) name, display name or uuid of the other node to query. If wrong, address will be ''


<code>
    Example:
        get_other_node_address('node-1')
    Returns:
        '192.168.0.1'
</code>
    """
    node = gossiper.query_by_name_or_uuid(other_node_name_or_uuid)
    if node is None:
        return ''
    return node['addr']


# Get all nodes that are defining a service sname and where the service is OK
# TODO: give a direct link to object, must copy it?
@export_evaluater_function(function_group=FUNCTION_GROUP)
def ok_nodes(group='', if_none=''):
    """**ok_nodes(group='', if_none='')** -> return a list with all alive nodes that match the group

 * group: (string) if set, will filter only nodes that are in this group
 * if_none: (string) if set to 'raise' then raise an Exception if no node is matching

<code>
    Example:
        ok_nodes(group='linux')
    Returns:
        [ ... ]  <- list of nodes objects
</code>
    """
    res = deque()
    if group == '':
        res = []
        for n in gossiper.nodes.values():  # note: nodes is a static dict
            if n['state'] != 'alive':
                continue
            res.append(n)
    else:
        nodes_uuids = gossiper.find_group_nodes(group)
        for node_uuid in nodes_uuids:
            n = gossiper.get(node_uuid)
            if n is not None:
                res.append(n)
    if if_none == 'raise' and len(res) == 0:
        # TODO: raise NoElementsExceptions()
        raise Exception('no node matching')
    # Be sure to always give nodes in the same order, if not, files will be generated too ofthen
    res = sorted(res, key=lambda node: node['uuid'])
    return res
