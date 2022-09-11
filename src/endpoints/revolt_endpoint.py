import asyncio
from typing import Callable, Coroutine
import aiohttp

import revolt
from revolt.ext import commands

from ..interface import *
from ..config import Config

import re

def cleanContent(self: revolt.Message) -> str:
	'''Clean content property stolen from discord.py'''
	def resolve_member(id: str) -> str:
		m = self.server.get_member(id)
		return f"@{m.nickname or m.name}" if m else "@deleted-user"

	def resolve_role(id: str) -> str:
		r = self.server.get_role(id)
		return f"@{r.name}" if r else "@deleted-role"

	def resolve_channel(id: str) -> str:
		c = self.server.get_channel(id)
		return f"#{c.name}" if c else "#deleted-channel"

	transforms = {
		'@': resolve_member,
		'@!': resolve_member,
		'#': resolve_channel,
		'@&': resolve_role,
	}

	def repl(match: re.Match) -> str:
		type = match[1]
		id = int(match[2])
		transformed = transforms[type](id)
		return transformed

	return re.sub(r'<(@[!&]?|#)([0-9A-Z]{26})>', repl, self.content)

PERMISSION_WRAPPERS = {
	Permission.ManageGuild: lambda perms: perms.manage_server
}

def compileEmbed(embed: Embed | None) -> revolt.SendableEmbed | None:
	if not embed: return None

	compiled = revolt.SendableEmbed(
		title=embed.title,
		description=embed.description,
		colour=str(embed.colour),
		url=embed.url,
		icon_url=embed.icon
	)

	if embed.footer:
		pass#compiled.set_footer(text=embed.footer)

	if embed.fields:
		for field in embed.fields:
			pass#compiled.add_field(name=field.name, value=field.value, inline=field.inline)

	return compiled

class Guild(IGuild): pass

class User(IUser):
	_usr: revolt.Member

	def __init__(self, member: revolt.Member, guild: Guild) -> None:
		super().__init__(
			guild,
			member.id, member.name,
			member.avatar.url if member.avatar else "", member.nickname,
			[Role(role, guild) for role in member.roles],
			member.bot
		)
		self._usr = member

	def __str__(self) -> str:
		return f"<@{self.id}>"

	@property
	def colour(self) -> Colour:
		for role in self.roles:
			if role.colour:
				return role.colour
		return Colour(255, 255, 255)

	@property
	def topRole(self) -> IRole:
		return self.roles[0]

	def hasPermission(self, permission: Permission) -> bool:
		return PERMISSION_WRAPPERS[permission](self._usr.roles[0].permissions)
	
	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._usr.send(content, embed=compileEmbed(embed))
			return
		await self._usr.send(
			content,
			embed=compileEmbed(embed),
			masquerade=revolt.Masquerade(masquerade.name, masquerade.avatar, str(masquerade.colour))
		)

class Message(IMessage):
	_msg: revolt.Message

	def __init__(self, msg: revolt.Message, guild: Guild) -> None:
		super().__init__(
			Channel(msg.channel, guild),
			msg.id, User(msg.author, guild),
			msg.content, cleanContent(msg),
			[attachment.url for attachment in msg.attachments],
			[] # TODO: implement embeds
		)
		self._msg = msg

	async def reply(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._msg.reply(content, embed=compileEmbed(embed))
			return
		await self._msg.reply(
			content,
			embed=compileEmbed(embed),
			masquerade=revolt.Masquerade(masquerade.name, masquerade.avatar, str(masquerade.colour))
		)

class Channel(IChannel):
	_chnl: revolt.TextChannel

	def __init__(self, channel: revolt.TextChannel, guild: Guild) -> None:
		super().__init__(guild, channel.id, channel.name)
		self._chnl = channel

	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is None or masquerade.name is None:
			await self._chnl.send(content, embed=compileEmbed(embed))
			return
		await self._chnl.send(
			content,
			embed=compileEmbed(embed),
			masquerade=revolt.Masquerade(masquerade.name, masquerade.avatar, str(masquerade.colour))
		)

class Role(IRole):
	_role: revolt.Role

	def __init__(self, role: revolt.Role, guild: Guild) -> None:
		colour = role.colour[1:] if role.colour else "ffffff"
		try:
			colour = (int(colour[i:(i + 2)], 16) for i in (0, 2, 4))
		except: # Revolt supports more complex colours than hex which would fail here
			colour = (255, 255, 255)

		super().__init__(
			guild,
			role.id, role.name,
			Colour(*colour)
		)
		self._role = role

class Emoji(IEmoji):
	_emji: None # revolt.py version with emojis not released yet

	def __init__(self, emoji: None, guild: Guild) -> None:
		super().__init__(guild, emoji.id, emoji.name, "")
		_emji = emoji

	def __str__(self) -> str:
		return self.url

class Guild(IGuild):
	_guild: revolt.Server

	def __init__(self, guild: revolt.Server) -> None:
		super().__init__(
			guild.id, guild.name,
			[Role(role, self) for role in guild.roles],
			[],#[Emoji(emoji, self) for emoji in guild.emojis], Emojis arent in the api fully yet
			[User(member, self) for member in guild.members]
		)
		self._guild = guild

	async def fetchMember(self, id: str) -> IUser | None:
		member = await self._guild.fetch_member(id)
		if member: return User(member, self)
		return None

UNWRAP = {
	IUser: revolt.Member,
	IMessage: revolt.Message,
	IChannel: revolt.TextChannel,
	IRole: revolt.Role,
	#IEmoji: discord.Emoji,
	Context: commands.Context
}
WRAP = {
	revolt.Member: lambda raw: User(raw, Guild(raw.server)),
	revolt.Message: lambda raw: Message(raw, Guild(raw.server)),
	revolt.TextChannel: lambda raw: Channel(raw, Guild(raw.server)),
	revolt.Role: lambda raw: Role(raw, Guild(raw.server)),
	#discord.Emoji: lambda raw: Emoji(raw, Guild(raw.guild)),
	commands.Context: lambda ctx: Context(Message(ctx.message, Guild(ctx.server)))
}

class Bot(IBot): pass

class BotImpl(commands.CommandsClient):
	def __init__(
		self, data: Bot,
		*args,
		help_command: commands.HelpCommand | None = None,
		case_insensitive: bool = False,
		**kwargs
	):
		super().__init__(*args, help_command=help_command, case_insensitive=case_insensitive, **kwargs)
		self.data = data
		self.ready = False

	async def get_prefix(self, _: revolt.Message) -> str:
		return self.data.config.prefix

	async def on_ready(self):
		self.ready = True
		if "onReady" in self.data.events: await self.data.events["onReady"]()

	async def on_message(self, message: revolt.Message):
		if not isinstance(message.channel, revolt.TextChannel) or not isinstance(message.author, revolt.Member): return
		if message.author.id == self.user.id: return # Don't run on our messages

		cmdEnd = message.content.find(" ")
		if cmdEnd == -1: cmdEnd = len(message.content)

		if (
			message.content.startswith(self.data.config.prefix) and
			(
				message.content[len(self.data.config.prefix):cmdEnd] in self.data.commands or
				message.content[len(self.data.config.prefix):cmdEnd] == "help"
			)
		):
			await self.process_commands(message)
		elif "onMessage" in self.data.events:
			await self.data.events["onMessage"](Message(message, Guild(message.server)))

	async def on_member_join(self, member: revolt.Member):
		if "onMemberJoin" in self.data.events:
			await self.data.events["onMemberJoin"](User(member, Guild(member.server)))

	async def on_member_leave(self, member: revolt.Member):
		if "onMemberLeave" in self.data.events:
			await self.data.events["onMemberLeave"](User(member, Guild(member.server)))

	async def on_member_update(self, _: revolt.Member, member: revolt.Member):
		if "onMemberUpdate" in self.data.events:
			await self.data.events["onMemberUpdate"](User(member, Guild(member.server)))

	async def on_role_delete(self, role: revolt.Role):
		if "onGuildRoleDelete" in self.data.events:
			await self.data.events["onGuildRoleDelete"](Role(role, Guild(role.server)))

	async def on_role_update(self, _: revolt.Role, role: revolt.Role):
		if "onGuildRoleUpdate" in self.data.events:
			await self.data.events["onGuildRoleUpdate"](Role(role, Guild(role.server)))

	''' Events not implemented yet
	async def on_guild_emojis_update(self, guild: discord.Guild, before: Sequence[discord.Emoji], after: Sequence[discord.Emoji]):
		if "onGuildEmojiCreate" not in self.events and "onGuildEmojiDelete" not in self.events: return

		beforeHash = {emoji.id: emoji for emoji in before}
		afterHash = {emoji.id: emoji for emoji in after}
		for id in beforeHash.keys() | afterHash.keys():
			if id not in beforeHash and "onGuildEmojiCreate" in self.events:
				await self.events["onGuildEmojiCreate"](Emoji(afterHash[id], Guild(afterHash[id].guild)))
			elif id not in afterHash and "onGuildEmojiDelete" in self.events:
				await self.events["onGuildEmojiDelete"](Emoji(beforeHash[id], Guild(beforeHash[id].guild)))
	'''

def wrap(func: Callable) -> Coroutine:
	async def wrapper(self: BotImpl, ctx: commands.Context, *args):
		print(ctx.args)
		if (
			not isinstance(ctx.channel, revolt.TextChannel) or
			not isinstance(ctx.message, revolt.Message) or
			not isinstance(ctx.message.author, revolt.Member)
		): return

		wrapped = []
		for arg in args:
			if type(arg) in WRAP:
				arg = WRAP[type(arg)](arg)
			wrapped.append(arg)
		await func(WRAP[commands.Context](ctx), *wrapped)

	baseSig = inspect.signature(wrapper).parameters
	wrapper.__signature__ = inspect.Signature([baseSig["self"]] + [
		inspect.Parameter(
			name=name,
			kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
			default=param.default,
			annotation=UNWRAP[param.annotation]
		) if param.annotation in UNWRAP else param for name, param in inspect.signature(func).parameters.items()
	])
	wrapper.__doc__ = func.__doc__
	wrapper.__name__ = func.__name__

	return wrapper

class Bot(IBot):
	def __init__(self, token: str, config: Config) -> None:
		super().__init__(token, config)

	async def start(self) -> None:
		for loop in self.loops:
			async def loopWrapper():
				while True:
					await loop.func()
					await asyncio.sleep(loop.interval)
			asyncio.create_task(loopWrapper())

		async with aiohttp.ClientSession() as session:
			self._bot = BotImpl(self, session, self.token, case_insensitive=True)

			for _, cmd in self.commands.items():
				self._bot.add_command(commands.Command(wrap(cmd), cmd.__name__, []))

			await self._bot.start()

	async def waitUntilReady(self) -> None:
		if self._bot.ready: return
		await self._bot.wait_for("ready")

	def getChannel(self, id: str) -> IChannel:
		channel = self._bot.get_channel(id)
		if channel and not isinstance(channel, revolt.TextChannel):
			raise ValueError("Unsupported channel")
		return Channel(channel, Guild(channel.server))
