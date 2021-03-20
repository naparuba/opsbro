import time
import threading
import traceback
import re

from opsbro.characters import CHARACTERS
from opsbro.module import HandlerModule
from opsbro.gossip import gossiper
from opsbro.threadmgr import threader
from opsbro.parameters import StringParameter, StringListParameter, IntParameter
from opsbro.compliancemgr import COMPLIANCE_STATES
from opsbro.util import PY3

# currently Python3 do not manage discord, as the lib is PY3 only
if PY3:
    # Local import, as we have . in sys.path when loading this file
    # NOTE: do NOT import in python2, as the synctax will be broken!
    from discord_bot import get_a_botclass
else:
    def get_a_bot_class(logger):
        raise Exception('The discord module is only available for python3, sorry.')


class DiscordHandlerModule(HandlerModule):
    implement = 'discord'
    
    parameters = {
        'enabled_if_group': StringParameter(default='discord'),
        'severities'      : StringListParameter(default=['ok', 'warning', 'critical', 'unknown']),
        'token'           : StringParameter(default=u''),
        'channel_id'      : IntParameter(default=0),
    }
    
    
    def __init__(self):
        super(DiscordHandlerModule, self).__init__()
        self.enabled = False
        self._token = ''
        self._channel_id = ''
        self._pending_messages_lock = threading.RLock()
        self._pending_messages = []
        self._bot_klass = None
        self._bot = None
        self._asyncio_lib = None
        self._ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    
    def prepare(self):
        if_group = self.get_parameter('enabled_if_group')
        self.enabled = gossiper.is_in_group(if_group)
        if self.enabled:
            self.logger.info('Module is enabled, we did use by looking at group: %s' % if_group)
        else:
            self.logger.info('Module is disabled, we did use by looking at group: %s' % if_group)
        self._token = self.get_parameter('token')
        self._channel_id = self.get_parameter('channel_id')
        
        if self.enabled:
            try:
                import asyncio
                self._asyncio_lib = asyncio
            except ImportError as exp:
                raise Exception('The discord module only works for Python 3 version (cannot load asyncio): %s' % exp)
    
    
    def launch(self):
        if not self.enabled:
            return
        # The creation can take time because we need to have the iohttp lib install first
        threader.create_and_launch(self._bot_creation_thread, name='Discord bot creation thread', part='discord', essential=True)
    
    
    def _bot_creation_thread(self):
        while True:
            try:
                if self._bot_klass is None:
                    try:
                        import aiohttp
                        self._bot_klass = get_a_botclass(self.logger)
                        self.logger.info('The Discord class was loaded: %s' % self._bot_klass)
                    except ImportError as exp:
                        self.logger.info('The module is currently unavailable because the discord librairy cannot be load: %s' % exp)
                        time.sleep(5)
                        continue
                if self._bot is None:
                    # We have the class, try to init the bot
                    self.logger.info('Preparing the asyncio loop environnement before starting the discord bot')
                    self._asyncio_lib.set_event_loop(self._asyncio_lib.new_event_loop())
                    self._bot = self._bot_klass(self._channel_id, self.logger)
                    # We are in a thread, so asyncio need a bit hack to work
                    
                    self._bot.loop.add_signal_handler = lambda x, y: None
                    self.logger.info('The Discord bot is created')
                    self._bot.run(self._token)
                    self.logger.info('The Discord bot is started')
            except Exception:
                self.logger.error('Creaton thread did failed with error: %s' % traceback.format_exc())
                time.sleep(1)
    
    
    def get_info(self):
        state = 'STARTED' if self.enabled else 'DISABLED'
        log = ''
        return {'configuration': self.get_config(), 'state': state, 'log': log}
    
    
    # def __try_to_send_message(self, slack, attachments, channel):
    #    r = slack.chat.post_message(channel=channel, text='', as_user=True, attachments=attachments)
    #    self.logger.debug('[SLACK] return of the send: %s %s %s' % (r.successful, r.__dict__['body']['channel'], r.__dict__['body']['ts']))
    
    # def __get_token(self):
    #    token = self.get_parameter('token')
    #    if not token:
    #        token = os.environ.get('DISCORD_TOKEN', '')
    #    return token
    
    def __send_discord_check(self, check):
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = check['output']
        content = self._ansi_escape.sub('', content)  # remove colors from shell
        # channel = self.get_parameter('channel')
        # colors = {'ok': 'good', 'warning': 'warning', 'critical': 'danger'}
        icon = {'ok': CHARACTERS.check, 'warning': CHARACTERS.double_exclamation, 'critical': CHARACTERS.cross}.get(check['state'], '')
        node_name = '%s (%s)' % (gossiper.name, gossiper.public_addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        # attachment = {"pretext": ' ', "text": content, 'color': colors.get(check['state'], '#764FA5'), 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        # fields = [
        #    {"title": "Node", "value": node_name, "short": True},
        #    {"title": "Check", "value": check['name'], "short": True},
        # ]
        # attachment['fields'] = fields
        # attachments = [attachment]
        # self.__do_send_message(slack, attachments, channel)
        self._bot.post_message('%s %s / Check %s' % (icon, node_name, check['name']), content)
    
    
    def __send_discord_group(self, group, group_modification):
        
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = 'The group %s was %s' % (group, group_modification)
        # channel = self.get_parameter('channel')
        colors = {'remove': 'danger', 'add': 'good'}
        node_name = '%s (%s)' % (gossiper.name, gossiper.public_addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        # attachment = {"pretext": ' ', "text": content, 'color': colors.get(group_modification, '#764FA5'), 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        # fields = [
        #    {"title": "Node", "value": node_name, "short": True},
        #    {"title": "Group:%s" % group_modification, "value": group, "short": True},
        # ]
        # attachment['fields'] = fields
        # attachments = [attachment]
        # self.__do_send_message(slack, attachments, channel)
        self._bot.post_message(node_name, content)
    
    
    def __send_discord_compliance(self, compliance):
        # token = self.__get_token()
        
        # if not token:
        #    self.logger.error('[SLACK] token is not configured on the slack module. skipping slack messages.')
        #    return
        # slack = Slacker(token)
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = 'The compliance %s changed from %s to %s' % (compliance.get_name(), compliance.get_state(), compliance.get_old_state())
        # channel = self.get_parameter('channel')
        icon = {
            COMPLIANCE_STATES.RUNNING     : CHARACTERS.hbar_dotted,
            COMPLIANCE_STATES.COMPLIANT   : CHARACTERS.check,
            COMPLIANCE_STATES.FIXED       : CHARACTERS.check,
            COMPLIANCE_STATES.ERROR       : CHARACTERS.cross,
            COMPLIANCE_STATES.PENDING     : '?',
            COMPLIANCE_STATES.NOT_ELIGIBLE: ''}.get(compliance.get_state())
        
        node_name = '%s (%s)' % (gossiper.name, gossiper.public_addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        # attachment = {"pretext": ' ', "text": content, 'color': color, 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        # fields = [
        #    {"title": "Node", "value": node_name, "short": True},
        #    {"title": "Compliance:%s" % compliance.get_name(), "value": compliance.get_state(), "short": True},
        # ]
        title = "%s %s Compliance:%s : %s" % (icon, node_name, compliance.get_name(), compliance.get_state())
        # attachment['fields'] = fields
        # attachments = [attachment]
        # self.__do_send_message(slack, attachments, channel)
        self._bot.post_message(title, content)
    
    
    # def __do_send_message(self, slack, attachments, channel):
    #     try:
    #         self.__try_to_send_message(slack, attachments, channel)
    #     except Exception as exp:
    #         self.logger.error('[SLACK] Cannot send alert: %s (%s) %s %s %s' % (exp, type(exp), str(exp), str(exp) == 'channel_not_found', exp.__dict__))
    #         # If it's just that the channel do not exists, try to create it
    #         if str(exp) == 'channel_not_found':
    #             try:
    #                 self.logger.info('[SLACK] Channel %s do no exists. Trying to create it.' % channel)
    #                 slack.channels.create(channel)
    #             except Exception as exp:
    #                 self.logger.error('[SLACK] Cannot create channel %s: %s' % (channel, exp))
    #                 return
    #             # Now try to resend the message
    #             try:
    #                 self.__try_to_send_message(slack, attachments, channel)
    #             except Exception as exp:
    #                 self.logger.error('[SLACK] Did create channel %s but we still cannot send the message: %s' % (channel, exp))
    #
    
    def handle(self, obj, event):
        if_group = self.get_parameter('enabled_if_group')
        self.enabled = gossiper.is_in_group(if_group)
        if not self.enabled:
            self.logger.debug('Discord module is not enabled, skipping check alert sent')
            return
        
        # self.logger.debug('Manage an obj event: %s (event=%s)' % (obj, event))
        self.logger.info('BOT OBJECT: %s' % self._bot)
        if not self._bot:
            self.logger.info('The bot is not ready, skipping event %s' % event)
            return
        
        # self._bot.post_message('Mon test', 'message test')
        # return
        evt_type = event['evt_type']
        if evt_type == 'check_execution':
            evt_data = event['evt_data']
            check_did_change = evt_data['check_did_change']
            if check_did_change:
                self.__send_discord_check(obj)
            return
        
        if evt_type == 'group_change':
            evt_data = event['evt_data']
            group_modification = evt_data['modification']
            self.__send_discord_group(obj, group_modification)
            return
        
        # Compliance: only when change, and only some switch cases should be
        # notify (drop useless changes)
        if evt_type == 'compliance_execution':
            evt_data = event['evt_data']
            compliance_did_change = evt_data['compliance_did_change']
            if compliance_did_change:
                self.__send_discord_compliance(obj)
            return
