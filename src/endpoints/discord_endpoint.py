import asyncio
import re

import discord
from discord.ext import commands

from ..interface import *
from ..config import Config

PERMISSION_WRAPPERS = {
	Permission.ManageGuild: lambda perms: perms.manage_guild
}

def compileEmbed(embed: Embed | None) -> discord.Embed | None:
	if not embed: return None

	compiled = discord.Embed(
		title=embed.title,
		description=embed.description,
		colour=discord.Colour.from_rgb(embed.colour.r, embed.colour.g, embed.colour.b),
		url=embed.url
	)

	if embed.footer:
		compiled.set_footer(text=embed.footer)
	if embed.icon:
		compiled.set_thumbnail(url=embed.icon)

	if embed.fields:
		for field in embed.fields:
			compiled.add_field(name=field.name, value=field.value, inline=field.inline)

	return compiled

class User(IUser):
	_usr: discord.Member

	def __init__(self, member: discord.Member) -> None:
		super().__init__(
			str(member.id), member.name,
			str(member.display_avatar), member.nick,
			[Role(role) for role in member.roles],
			member.bot
		)
		self._usr = member

	def __str__(self) -> str:
		return f"<@{self.id}>"

	def hasPermission(self, permission: Permission) -> bool:
		return PERMISSION_WRAPPERS[permission](self._usr.guild_permissions)
	
	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._usr.send(content, embed=compileEmbed(embed))
			return
		await self._usr.send(f"{masquerade.name} | {content}", embed=compileEmbed(embed))

class Guild(IGuild):
	_guild: discord.Guild

	def __init__(self, guild: discord.Guild) -> None:
		super().__init__(
			str(guild.id), guild.name,
			[Role(role) for role in guild.roles],
			[Emoji(emoji) for emoji in guild.emojis],
			[User(member) for member in guild.members]
		)
		self._guild = guild

	async def fetchMember(self, id: str) -> IUser | None:
		member = await self._guild.fetch_member(int(id))
		if member: return User(member)
		return None

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

	async def reply(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._msg.reply(content, embed=compileEmbed(embed))
			return
		await self._msg.reply(f"{masquerade.name} | {content}", embed=compileEmbed(embed))

class Channel(IChannel):
	_chnl: discord.TextChannel

	def __init__(self, channel: discord.TextChannel) -> None:
		super().__init__(Guild(channel.guild), str(channel.id), channel.name)
		self._chnl = channel

	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._chnl.send(content, embed=compileEmbed(embed))
			return
		await self._chnl.send(f"{masquerade.name} | {content}", embed=compileEmbed(embed))

class Role(IRole):
	_role: discord.Role

	def __init__(self, role: discord.Role) -> None:
		super().__init__(str(role.id), role.name, Colour(role.colour.r, role.colour.g, role.colour.b))
		self._role = role

class Emoji(IEmoji):
	_emji: discord.Emoji

	def __init__(self, emoji: discord.Emoji) -> None:
		super().__init__(str(emoji.id), emoji.name, emoji.url)
		_emji = emoji

	def __str__(self) -> str:
		return self.url

UNWRAP = {
	IUser: discord.Member,
	IMessage: discord.Message,
	IChannel: discord.TextChannel,
	IRole: discord.Role,
	IEmoji: discord.Emoji,
	Context: commands.Context
}
WRAP = {
	discord.Member: User,
	discord.Message: Message,
	discord.TextChannel: Channel,
	discord.Role: Role,
	discord.Emoji: Emoji,
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

		@bot.event
		async def on_message(message: discord.Message):
			if not isinstance(message.channel, discord.TextChannel) or not isinstance(message.author, discord.Member): return
			if message.author.id == self._bot.user.id: return # Don't run on our messages

			if "onMessage" in self.events:
				await self.events["onMessage"](WRAP[discord.Message](message))
			
			ctx = await self._bot.get_context(message)
			await self._bot.invoke(ctx) # type: ignore

		self._bot = bot

	async def start(self) -> None:
		for loop in self.loops:
			async def loopWrapper():
				while True:
					await loop.func()
					await asyncio.sleep(loop.interval)
			asyncio.create_task(loopWrapper())

		await self._bot.start(self.token)

	async def waitUntilReady(self) -> None:
		await self._bot.wait_until_ready()

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

	def getChannel(self, id: str) -> IChannel:
		return self._bot.get_channel()
