import os
import sys
import threading
import time

from opsbro.threadmgr import threader
from opsbro.gossip import gossiper


def get_a_botclass(logger):
    # NOTE: this directory is no more in sys.path, and we want to to lazy load, so need to hack a bit the
    # sys.path
    my_path = os.path.dirname(__file__)
    if my_path not in sys.path:
        sys.path.insert(0, my_path)
    # Lazy import
    import aiohttp
    import discord
    from discord.ext import commands
    discord.client.log = logger
    
    import logging
    
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    
    # handler = logging.FileHandler(filename='/tmp/discord.log', encoding='utf-8', mode='w')
    # handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    # logger.addHandler(handler)
    
    class DiscoBot(commands.Bot):
        def __init__(self, channel_name, logger):
            intents = discord.Intents.default()
            intents.members = True
            self.logger = logger
            connector = aiohttp.TCPConnector(verify_ssl=False)
            super().__init__(command_prefix="!", description='OpsBro bot', intents=intents, connector=connector)
            self._post_channel = None
            self._channel_name = channel_name
            self.logger.info('Discord bot create with channel: %s' % self._channel_name)
            self._pending_messages_lock = threading.RLock()
            self._pending_messages = []
            
            threader.create_and_launch(self.bot_consumption_thread, name='Discord bot message sending', part='discord', essential=True)
        
        
        def _get_channel(self):
            channel = self.get_channel(self._channel_name)
            logger.info('GIVE CHANNEL: %s' % channel)
            return channel
            # if self._post_channel is not None:
            #     self.logger.info('_get_channel:: %s' % self._post_channel)
            #     return self._post_channel
            #
            # for channel in self.get_all_channels():
            #     self.logger('_get_channel::We can see channel: %s' % (channel))
            #     if channel.name == self._channel_id:
            #         self._post_channel = channel
            #         self.logger('_get_channel:: Did found our channel :%s' % self._post_channel)
            #         return self._post_channel
            # self.logger.info('_get_channel:: no channel founded')
            # return None
        
        
        async def _post_message(self, title, txt):
            self.logger.info('_post_message::Calling post message: %s' % txt)
            channel = self._get_channel()
            if channel is None:
                self.logger.info('_post_message::We are not in a channel, please select one')
                return
            self.logger.info('_post_message::Posting mesage: %s in channel %s' % (txt, channel))
            # Maybe we have waiting messages
            
            embed = discord.Embed(title=title, description=txt, footer='From opsbro')
            await channel.send('', embed=embed)
        
        
        def bot_consumption_thread(self):
            # asyncio.set_event_loop(asyncio.new_event_loop())
            # loop = asyncio.get_event_loop()
            while True:
                # fast switch
                with self._pending_messages_lock:
                    pending_messages = self._pending_messages
                    self._pending_messages = []
                if not pending_messages:
                    time.sleep(1)
                    continue
                self.logger.info('Managing %s messages with loop %s' % (len(pending_messages), self.loop))
                for (title, message) in pending_messages:
                    self.loop.create_task(self._post_message(title, message))
                    # self.loop.run_in_executor(None, self._post_message, message)
                time.sleep(1)
        
        
        def post_message(self, title, txt):
            self.logger.info('Call post_message: %s' % txt)
            with self._pending_messages_lock:
                self._pending_messages.append((title, txt))
        
        
        # Called when connected
        async def on_ready(self):
            # NOTE: on ready means that we are not in a channel currently
            node_name = '%s (%s)' % (gossiper.name, gossiper.public_addr)
            if gossiper.display_name:
                node_name = '%s [%s]' % (node_name, gossiper.display_name)
            await self._post_message('%s Daemon connected' % node_name, 'Daemon is connected at discord as: %s ' % (self.user.name))
        
        
        # Called when connected
        async def on_error(self, event):
            self.logger.error('WE DO HAVE AN ERROR EVENT: %s' % event)
        
        
        async def on_message(self, message):
            self.logger.info('NEW MESSAGE RECEIVED: %s' % message)
            if message.author.bot:
                self.logger.debug('Last message was from a bot, skipping')
                return
            message_string = message.content
            if message_string.startswith('!'):
                await message.channel.send('Special command %s' % message.content)
                return
            await message.channel.send('ECHO: %s' % message.content)
        
        
        # async def on_member_join(self, member):
        #    txt = "L'utilisateur %s a rejoint le serveur !" % member.display_name
        #    await self._post_message('Login',txt)
        
        @commands.command(name='add')
        async def add(self, ctx, left: int, right: int):
            """Adds two numbers together."""
            await ctx.send(left + right)
    
    return DiscoBot
