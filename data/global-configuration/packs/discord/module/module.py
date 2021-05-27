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
    try:
        from discord_bot import get_a_botclass
    except SyntaxError:  # old python3 versions
        def get_a_bot_class(logger):
            raise Exception('The discord module is only available for python3, sorry.')
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
        self._stacking_period = 5  # stack messages up to 5 seconds
    
    
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
        
        # Stack messages up to X seconds, and send them in a unique bulk message
        threader.create_and_launch(self._stacking_messages_thread, name='Discord messages thread', part='discord', essential=True)
    
    
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
    
    
    def _stacking_messages_thread(self):
        while True:
            # Fast switch to get our messages
            with self._pending_messages_lock:
                pending_messages = self._pending_messages
                self._pending_messages = []
            
            # Sleep if no messages
            if len(pending_messages) == 0:
                self.logger.debug('No messages this turn, go sleep')
                time.sleep(self._stacking_period)
                continue
            
            # Or if the bot is not connected currently
            if not self._bot:
                self.logger.info('The bot is not ready, skipping sending events')
                time.sleep(self._stacking_period)
                continue
            
            # NOTE: in the loop, maybe the name can change during run
            node_name = '%s (%s)' % (gossiper.name, gossiper.public_addr)
            if gossiper.display_name:
                node_name = '%s [%s]' % (node_name, gossiper.display_name)
            
            content = u'- ' + u'\n - '.join(pending_messages)
            self.logger.info('Sending message: %s' % content)
            try:
                self._bot.post_message(node_name, content)
            except Exception:
                self.logger.error('Creaton thread did failed with error: %s' % traceback.format_exc())
                time.sleep(1)
            time.sleep(self._stacking_period)
    
    
    def get_info(self):
        state = 'STARTED' if self.enabled else 'DISABLED'
        log = ''
        return {'configuration': self.get_config(), 'state': state, 'log': log}
    
    
    def __send_discord_check(self, check):
        content = check['output']
        content = self._ansi_escape.sub('', content)  # remove colors from shell
        icon = {'ok': CHARACTERS.check, 'warning': CHARACTERS.double_exclamation, 'critical': CHARACTERS.cross}.get(check['state'], '')
        
        with self._pending_messages_lock:
            message = '%s : %s' % ('%s Check %s' % (icon, check['name']), content)
            self._pending_messages.append(message)
    
    
    def __send_discord_group(self, group, group_modification):
        content = 'The group %s was %s' % (group, group_modification)
        with self._pending_messages_lock:
            self._pending_messages.append(content)
    
    
    def __send_discord_compliance(self, compliance):
        content = 'The compliance %s changed from %s to %s' % (compliance.get_name(), compliance.get_state(), compliance.get_old_state())
        
        icon = {
            COMPLIANCE_STATES.RUNNING     : CHARACTERS.hbar_dotted,
            COMPLIANCE_STATES.COMPLIANT   : CHARACTERS.check,
            COMPLIANCE_STATES.FIXED       : CHARACTERS.check,
            COMPLIANCE_STATES.ERROR       : CHARACTERS.cross,
            COMPLIANCE_STATES.PENDING     : '?',
            COMPLIANCE_STATES.NOT_ELIGIBLE: ''}.get(compliance.get_state())
        
        title = "%s Compliance:%s : %s" % (icon, compliance.get_name(), compliance.get_state())
        with self._pending_messages_lock:
            message = u'%s \n   -> %s' % (title, content)
            self._pending_messages.append(message)
    
    
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
