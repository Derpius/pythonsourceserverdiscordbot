import asyncio

import discord
from discord.ext import commands

from ...interface import *

from .compileEmbed import compileEmbed
from . import webhookService

PERMISSION_WRAPPERS = {
	Permission.ManageGuild: lambda perms: perms.manage_guild
}

class Guild(IGuild): pass

class User(IUser):
	_usr: discord.User | discord.Member

	def __init__(self, user: discord.User | discord.Member, guild: Guild) -> None:
		super().__init__(
			guild,
			str(user.id), user.name,
			str(user.display_avatar), user.nick if isinstance(user, discord.Member) else None,
			[Role(role, guild) for role in user.roles] if isinstance(user, discord.Member) else [],
			user.bot
		)
		self._usr = user

	def __str__(self) -> str:
		return f"<@{self.id}>"

	@property
	def colour(self) -> Colour:
		roles = self.roles[1:] # remove @everyone

		for role in reversed(roles):
			if role.colour:
				return role.colour
		return Colour(255, 255, 255)

	@property
	def topRole(self) -> IRole:
		return self.roles[-1]

	def hasPermission(self, permission: Permission) -> bool:
		if not isinstance(self._usr, discord.Member):
			return False

		return PERMISSION_WRAPPERS[permission](self._usr.guild_permissions)
	
	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		if masquerade is not None:
			raise ValueError("Masquerades on Discord require webhooks to mimic functionality, which are not supported in DMs")

		await self._usr.send(content, embed=compileEmbed(embed))

class Message(IMessage): pass
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

	async def reply(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> Message:
		if masquerade is not None:
			raise ValueError("Masquerades on Discord require webhooks to mimic functionality, which cannot reply to messages")

		return Message(await self._msg.reply(content, embed=compileEmbed(embed)), self.guild)

	async def edit(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		await self._msg.edit(content=content, embed=compileEmbed(embed))

class Channel(IChannel):
	_chnl: discord.TextChannel

	def __init__(self, channel: discord.TextChannel, guild: Guild) -> None:
		super().__init__(guild, str(channel.id), channel.name)
		self._chnl = channel

	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> Message:
		if masquerade is None or masquerade.name is None:
			return Message(await self._chnl.send(content, embed=compileEmbed(embed)), self.guild)

		try:
			webhook = await webhookService.connect(self._chnl)
		except discord.Forbidden:
			return Message(
				await self._chnl.send(
					f"{masquerade.name} | {content}",
					embed=compileEmbed(embed)
				),
				self.guild
			)
		else:
			return Message(
				await webhook.send(
					content,
					embed=compileEmbed(embed),
					username=masquerade.name,
					avatar_url=masquerade.avatar,
					wait=True,
					allowed_mentions=discord.AllowedMentions(everyone=False)
				),
				self.guild
			)

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
			[User(member, self) for member in guild.members],
			User(guild.owner, self) if guild.owner else None
		)
		self._guild = guild

	async def fetchMember(self, id: str) -> IUser | None:
		member = await self._guild.fetch_member(int(id))
		if member: return User(member, self)
		return None
