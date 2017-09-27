from opsbro.module import ConnectorModule
from opsbro.parameters import StringParameter, BoolParameter
from opsbro.gossip import gossiper


class ShinkenEnterpriseModule(ConnectorModule):
    implement = 'shinken-enterprise'
    
    parameters = {
        'enabled'                : BoolParameter(default=False),
        'enterprise_callback_uri': StringParameter(default=''),
    }
    
    
    # We only work at the stopping phase, when all is finish, to get back our discovery
    def stopping_agent(self):
        enabled = self.get_parameter('enabled')
        if not enabled:
            return
        with gossiper.groups_lock:
            groups = gossiper.groups[:]
        self.logger.info('Pushing back ours groups and discovery informations to Shinken Enterprise')
        # TODO: push to shinken now :)
