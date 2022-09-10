from dataclasses import dataclass
import re

import discord
from discord.ext import commands

from ..interface import *
from ..config import Config

@dataclass
class User(IUser):
	_usr: discord.Member

@dataclass
class Message(IMessage):
	_msg: discord.Message

	async def reply(self, message: str) -> None:
		await self._msg.reply(message)

@dataclass
class Channel(IChannel):
	_chnl: discord.TextChannel

	async def send(self, message: str) -> None:
		await self._chnl.send(message)

UNWRAP = {
	IUser: discord.Member,
	IChannel: discord.TextChannel,
	Context: commands.Context
}
WRAP = {
	discord.Member: lambda member: User(member.id, member.name, str(member.avatar_url), member.nick, member),
	discord.Message: lambda message: Message(
		Channel(message.channel.id, message.channel.name, message.channel),
		message.id,
		User(
			message.author.id,
			message.author.name,
			str(message.author.avatar_url),
			message.author.nick,
			message.author
		),
		message.content,
		message.clean_content,
		[attachment.url for attachment in message.attachments],
		[], # TODO: embed support
		message
	),
	discord.TextChannel: lambda channel: Channel(channel.id, channel.name, channel),
	commands.Context: lambda ctx: Context(Message(
		Channel(ctx.channel.id, ctx.channel.name, ctx.channel),
		ctx.message.id,
		User(
			ctx.message.author.id,
			ctx.message.author.name,
			str(ctx.message.author.avatar_url),
			ctx.message.author.nick,
			ctx.message.author
		),
		ctx.message.content,
		ctx.message.clean_content,
		[attachment.url for attachment in ctx.message.attachments],
		[], # TODO: embed support
		ctx.message
	))
}

class Bot(IBot):
	def __init__(self, token: str, config: Config) -> None:
		super().__init__(token, config)

		# Set up intents
		intents = discord.Intents.default()
		intents.members = True
		#intents.message_content = True

		# Set up bot
		bot = commands.Bot(config.prefix, case_insensitive=True, intents=intents)

		@bot.event
		async def on_ready():
			await bot.wait_until_ready()
			if "onReady" in self.events: await self.events["onReady"](self)

		commandPattern = re.compile("^[^\s]*")
		@bot.event
		async def on_message(message: discord.Message):
			if not isinstance(message.channel, discord.TextChannel) or not isinstance(message.author, discord.Member): return
			if "onMessage" in self.events:
				await self.events["onMessage"](WRAP[discord.Message](message))
			await bot.process_commands(message)
		
		self._bot = bot
	
	def run(self) -> None:
		self._bot.run(self.token)

	def command(self, func: Coroutine) -> None:
		super().command(func)

		sig = inspect.Signature([
			inspect.Parameter(
				name,
				inspect.Parameter.POSITIONAL_OR_KEYWORD,
				default=param.default,
				annotation=UNWRAP[param.annotation]
			) if param.annotation in UNWRAP else param for name, param in inspect.signature(func).parameters.items()
		])

		async def wrapper(ctx: commands.Context, *args):
			if (
				not isinstance(ctx.channel, discord.TextChannel) or
				not isinstance(ctx.message, discord.Message) or
				not isinstance(ctx.message.author, discord.Member)
			): return

			wrapped = []
			for arg in args:
				if type(arg) in WRAP:
					arg = WRAP[type(arg)](arg)
				wrapped.append(arg)
			await func(WRAP[commands.Context](ctx), *wrapped)

		wrapper.__doc__ = func.__doc__
		wrapper.__signature__ = sig
		self._bot.add_command(commands.Command(wrapper, name=func.__name__))
