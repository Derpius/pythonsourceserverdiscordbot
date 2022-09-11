import asyncio
import re
from typing import Sequence

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
		colour=discord.Colour(int(embed.colour)),
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

class Guild(IGuild): pass

class User(IUser):
	_usr: discord.Member

	def __init__(self, member: discord.Member, guild: Guild) -> None:
		super().__init__(
			guild,
			str(member.id), member.name,
			str(member.display_avatar), member.nick,
			[Role(role, guild) for role in member.roles],
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

class Message(IMessage):
	_msg: discord.Message

	def __init__(self, msg: discord.Message, guild: Guild) -> None:
		super().__init__(
			Channel(msg.channel, guild),
			str(msg.id), User(msg.author, guild),
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

	def __init__(self, channel: discord.TextChannel, guild: Guild) -> None:
		super().__init__(guild, str(channel.id), channel.name)
		self._chnl = channel

	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._chnl.send(content, embed=compileEmbed(embed))
			return
		await self._chnl.send(f"{masquerade.name} | {content}", embed=compileEmbed(embed))

class Role(IRole):
	_role: discord.Role

	def __init__(self, role: discord.Role, guild: Guild) -> None:
		super().__init__(
			guild,
			str(role.id), role.name,
			Colour(role.colour.r, role.colour.g, role.colour.b) if role.colour.value else None
		)
		self._role = role

class Emoji(IEmoji):
	_emji: discord.Emoji

	def __init__(self, emoji: discord.Emoji, guild: Guild) -> None:
		super().__init__(guild, str(emoji.id), emoji.name, emoji.url)
		_emji = emoji

	def __str__(self) -> str:
		return self.url

class Guild(IGuild):
	_guild: discord.Guild

	def __init__(self, guild: discord.Guild) -> None:
		super().__init__(
			str(guild.id), guild.name,
			[Role(role, self) for role in guild.roles],
			[Emoji(emoji, self) for emoji in guild.emojis],
			[User(member, self) for member in guild.members]
		)
		self._guild = guild

	async def fetchMember(self, id: str) -> IUser | None:
		member = await self._guild.fetch_member(int(id))
		if member: return User(member, self)
		return None

UNWRAP = {
	IUser: discord.Member,
	IMessage: discord.Message,
	IChannel: discord.TextChannel,
	IRole: discord.Role,
	IEmoji: discord.Emoji,
	Context: commands.Context
}
WRAP = {
	discord.Member: lambda raw: User(raw, Guild(raw.guild)),
	discord.Message: lambda raw: Message(raw, Guild(raw.guild)),
	discord.TextChannel: lambda raw: Channel(raw, Guild(raw.guild)),
	discord.Role: lambda raw: Role(raw, Guild(raw.guild)),
	discord.Emoji: lambda raw: Emoji(raw, Guild(raw.guild)),
	commands.Context: lambda ctx: Context(Message(ctx.message, Guild(ctx.guild)))
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
			if "onReady" in self.events: await self.events["onReady"]()

		@bot.event
		async def on_message(message: discord.Message):
			await bot.wait_until_ready()

			if not isinstance(message.channel, discord.TextChannel) or not isinstance(message.author, discord.Member): return
			if message.author.id == self._bot.user.id: return # Don't run on our messages

			cmdEnd = message.content.find(" ")
			if cmdEnd == -1: cmdEnd = len(message.content)

			if (
				message.content.startswith(config.prefix) and
				message.content[len(config.prefix):cmdEnd] in self.commands
			):
				ctx = await self._bot.get_context(message)
				await self._bot.invoke(ctx)
			elif "onMessage" in self.events:
				await self.events["onMessage"](Message(message, Guild(message.guild)))

		@bot.event
		async def on_member_join(member: discord.Member):
			if "onMemberJoin" in self.events:
				await self.events["onMemberJoin"](User(member, Guild(member.guild)))

		@bot.event
		async def on_member_remove(member: discord.Member):
			if "onMemberLeave" in self.events:
				await self.events["onMemberLeave"](User(member, Guild(member.guild)))

		@bot.event
		async def on_member_update(_: discord.Member, member: discord.Member):
			if "onMemberUpdate" in self.events:
				await self.events["onMemberUpdate"](User(member, Guild(member.guild)))

		@bot.event
		async def on_guild_role_create(role: discord.Role):
			if "onGuildRoleCreate" in self.events:
				await self.events["onGuildRoleCreate"](Role(role, Guild(role.guild)))

		@bot.event
		async def on_guild_role_delete(role: discord.Role):
			if "onGuildRoleDelete" in self.events:
				await self.events["onGuildRoleDelete"](Role(role, Guild(role.guild)))

		@bot.event
		async def on_guild_role_update(_: discord.Role, role: discord.Role):
			if "onGuildRoleUpdate" in self.events:
				await self.events["onGuildRoleUpdate"](Role(role, Guild(role.guild)))

		@bot.event
		async def on_guild_emojis_update(guild: discord.Guild, before: Sequence[discord.Emoji], after: Sequence[discord.Emoji]):
			if "onGuildEmojiCreate" not in self.events and "onGuildEmojiDelete" not in self.events: return

			beforeHash = {emoji.id: emoji for emoji in before}
			afterHash = {emoji.id: emoji for emoji in after}
			for id in beforeHash.keys() | afterHash.keys():
				if id not in beforeHash and "onGuildEmojiCreate" in self.events:
					await self.events["onGuildEmojiCreate"](Emoji(afterHash[id], Guild(afterHash[id].guild)))
				elif id not in afterHash and "onGuildEmojiDelete" in self.events:
					await self.events["onGuildEmojiDelete"](Emoji(beforeHash[id], Guild(beforeHash[id].guild)))

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
		channel = self._bot.get_channel(int(id))
		if channel and not isinstance(channel, discord.TextChannel):
			raise ValueError("Unsupported channel")
		return Channel(channel, Guild(channel.guild))
