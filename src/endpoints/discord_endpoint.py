from dataclasses import dataclass
import re

import discord
from discord.ext import commands

from ..interface import *
from ..config import Config

PERMISSION_WRAPPERS = {
	Permission.ManageGuild: lambda perms: perms.manage_guild
}

class User(IUser):
	_usr: discord.Member

	def __init__(self, member: discord.Member) -> None:
		super().__init__(str(member.id), member.name, str(member.display_avatar), member.nick)
		self._usr = member

	def __str__(self) -> str:
		return f"<@{self.id}>"

	def hasPermission(self, permission: Permission) -> bool:
		return PERMISSION_WRAPPERS[permission](self._usr.guild_permissions)
	
	async def send(self, content: str) -> None:
		return await self._usr.send(content)

class Guild(IGuild):
	_guild: discord.Guild

	def __init__(self, guild: discord.Guild) -> None:
		super().__init__(str(guild.id), guild.name)
		self._guild = guild

	async def fetchMember(self, id: str) -> IUser | None:
		return await self._guild.fetch_member(int(id))

class Message(IMessage):
	_msg: discord.Message

	def __init__(self, msg: discord.Message) -> None:
		super().__init__(
			Channel(msg.channel),
			str(msg.id), User(msg.author),
			msg.content, msg.clean_content,
			[str(attachment) for attachment in msg.attachments],
			[] # TODO: implement embeds
		)
		self._msg = msg

	async def reply(self, message: str, masquerade: Masquerade | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._msg.reply(message)
			return
		await self._msg.reply(f"{masquerade.name} | {message}")

class Channel(IChannel):
	_chnl: discord.TextChannel

	def __init__(self, channel: discord.TextChannel) -> None:
		super().__init__(Guild(channel.guild), str(channel.id), channel.name)
		self._chnl = channel

	async def send(self, message: str, masquerade: Masquerade | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._chnl.send(message)
			return
		await self._chnl.send(f"{masquerade.name} | {message}")

UNWRAP = {
	IUser: discord.Member,
	IChannel: discord.TextChannel,
	Context: commands.Context
}
WRAP = {
	discord.Member: User,
	discord.Message: Message,
	discord.TextChannel: Channel,
	commands.Context: lambda ctx: Context(Message(ctx.message))
}

class Bot(IBot):
	def __init__(self, token: str, config: Config) -> None:
		super().__init__(token, config)

		# Set up intents
		intents = discord.Intents.default()
		intents.members = True
		intents.message_content = True

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
			
			ctx = await self._bot.get_context(message)
			await self._bot.invoke(ctx) # type: ignore
		
		self._bot = bot
	
	def run(self) -> None:
		self._bot.run(self.token)

	def command(self, func: Coroutine) -> None:
		super().command(func)

		sig = inspect.Signature([
			commands.Parameter(
				name=name,
				kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
				default=param.default,
				annotation=UNWRAP[param.annotation] if param.annotation in UNWRAP else param.annotation
			) for name, param in inspect.signature(func).parameters.items()
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
		self._bot.command(name=func.__name__)(wrapper)
