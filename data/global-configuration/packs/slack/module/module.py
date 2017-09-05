import time
import os

try:
    import jinja2
except ImportError:
    jinja2 = None

from slacker import Slacker

from opsbro.module import HandlerModule
from opsbro.gossip import gossiper
from opsbro.parameters import BoolParameter, StringParameter, StringListParameter


class SlackHandlerModule(HandlerModule):
    implement = 'slack'
    
    parameters = {
        'enabled'   : BoolParameter(default=False),
        'severities': StringListParameter(default=['ok', 'warning', 'critical', 'unknown']),
        'contacts'  : StringListParameter(default=['admin@mydomain.com']),
        'token'     : StringParameter(default=''),
        'channel'   : StringParameter(default='#alerts'),
    }
    
    
    def __init__(self):
        super(SlackHandlerModule, self).__init__()
    
    
    def try_to_send_message(self, slack, attachments, channel):
        r = slack.chat.post_message(channel=channel, text='', as_user=True, attachments=attachments)
        self.logger.debug('[SLACK] return of the send: %s %s %s' % (r.successful, r.__dict__['body']['channel'], r.__dict__['body']['ts']))
    
    
    def send_slack(self, handler, check):
        token = self.get_parameter('token')
        if not token:
            token = os.environ.get('SLACK_TOKEN', '')
        
        if token:
            self.logger.error('[SLACK] token is not configured on the handler %s skipping slack messages.' % handler['name'])
            return
        slack = Slacker(token)
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = check['output']
        channel = self.get_parameter('channel')
        colors = {'ok': 'good', 'warning': 'warning', 'critical': 'danger'}
        node_name = '%s (%s)' % (gossiper.name, gossiper.addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        attachment = {"pretext": ' ', "text": content, 'color': colors.get(check['state'], '#764FA5'), 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        fields = [
            {"title": "Node", "value": node_name, "short": True},
            {"title": "Check", "value": check['name'], "short": True},
        ]
        attachment['fields'] = fields
        attachments = [attachment]
        try:
            self.try_to_send_message(slack, attachments, channel)
        except Exception, exp:
            self.logger.error('[SLACK] Cannot send alert: %s (%s) %s %s %s' % (exp, type(exp), str(exp), str(exp) == 'channel_not_found', exp.__dict__))
            # If it's just that the channel do not exists, try to create it
            if str(exp) == 'channel_not_found':
                try:
                    self.logger.info('[SLACK] Channel %s do no exists. Trying to create it.' % channel)
                    slack.channels.create(channel)
                except Exception, exp:
                    self.logger.error('[SLACK] Cannot create channel %s: %s' % (channel, exp))
                    return
                # Now try to resend the message
                try:
                    self.try_to_send_message(slack, attachments, channel)
                except Exception, exp:
                    self.logger.error('[SLACK] Did create channel %s but we still cannot send the message: %s' % (channel, exp))
    
    
    def handle(self, handler, obj, event):
        enabled = self.get_parameter('enabled')
        if not enabled:
            self.logger.debug('Mail module is not enabled, skipping check alert sent')
            return
        
        self.logger.info('Manage an obj event: %s (event=%s)' % (obj, event))
        
        evt_type = event['evt_type']
        if evt_type == 'check_execution':
            evt_data = event['evt_data']
            check_did_change = evt_data['check_did_change']
            if check_did_change:
                self.send_slack(handler, obj)
