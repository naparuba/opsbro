# This example requires the 'members' privileged intents

import sys
import os

sys.path.insert(0, '.')

import discord
from discord.ext import commands


class DiscoBot(commands.Bot):
    def __init__(self, channel_name):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", description='OpsBro bot', intents=intents)
        self._post_channel = None
        self._channel_name = channel_name
        
        self._waiting_messages = []
    
    
    def _get_channel(self):
        if self._post_channel is not None:
            return self._post_channel
        
        for channel in self.get_all_channels():
            print('On server CHANNEL: %s' % (channel))
            if channel.name == self._channel_name:
                print('Did found our channel :%s' % self._channel_name)
                self._post_channel = channel
                return self._post_channel
        
        return None
    
    
    async def _post_message(self, txt):
        channel = self._get_channel()
        if channel is None:
            logger.info('We are not in a channel, plase select one')
            return
        # Maybe we have waiting messages
        await channel.send(txt)
    
    
    # Called when connected
    async def on_ready(self):
        # NOTE: on ready means that we are not in a channel currently
        
        await self._post_message('Logged in as: %s / %s' % (self.user.name, self.user.id))
    
    
    async def on_message(self, message):
        print('NEW MESSAGE RECEIVED: %s' % message)
        if message.author.bot:
            print('WAS FROM ME')
            return
        message_string = message.content
        if message_string.startswith('!'):
            await message.channel.send('Special command %s' % message.content)
            return
        await message.channel.send('ECHO: %s' % message.content)
    
    
    async def on_member_join(self, member):
        txt = f"L'utilisateur {member.display_name} a rejoint le serveur !"
        await self._post_message(txt)
    
    
    @commands.command(name='add')
    async def add(self, ctx, left: int, right: int):
        """Adds two numbers together."""
        await ctx.send(left + right)


TOKEN = os.environ.get('TOKEN')
CHANNEL = os.environ.get('CHANNEL')  # test-jean

bot = DiscoBot(CHANNEL)
bot.run(TOKEN)
