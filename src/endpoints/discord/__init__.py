import inspect
import traceback
import asyncio
from typing import Coroutine, Sequence

import discord
from discord.ext import commands

from ...interface import *
from ...config import Config

from .wrappers import Guild, User, Message, Channel, Role, Emoji
from .webhookService import WebhookService

UNWRAP = {
	IUser: discord.Member,
	IMessage: discord.Message,
	IChannel: discord.TextChannel,
	IRole: discord.Role,
	IEmoji: discord.Emoji,
	Context: commands.Context
}

WRAP = {
	discord.Member: lambda bot, raw: User(raw, Guild(raw.guild)),
	discord.Message: lambda bot, raw: Message(raw, Guild(raw.guild)),
	discord.TextChannel: lambda bot, raw: Channel(raw, Guild(raw.guild), bot._webhooks),
	discord.Role: lambda bot, raw: Role(raw, Guild(raw.guild)),
	discord.Emoji: lambda bot, raw: Emoji(raw, Guild(raw.guild)),
	commands.Context: lambda bot, ctx: Context(Message(ctx.message, Guild(ctx.guild)))
}

def wrapLoop(loop):
	async def wrapper():
		while True:
			await loop.func()
			await asyncio.sleep(loop.interval)
	return wrapper

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
				(
					message.content[len(config.prefix):cmdEnd] in self.commands or
					message.content[len(config.prefix):cmdEnd] == "help"
				)
			):
				ctx = await self._bot.get_context(message)
				await self._bot.invoke(ctx)
			elif "onMessage" in self.events:
				await self.events["onMessage"](Message(message, Guild(message.guild)))
		
		@bot.event
		async def on_command_error(ctx: commands.Context, err: commands.CommandError):
			traceback.print_exception(type(err), err, err.__traceback__)

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
		self._webhooks = WebhookService(self._bot.user)

	async def start(self) -> None:
		for loop in self.loops:
			asyncio.create_task(wrapLoop(loop)())

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
					arg = WRAP[type(arg)](arg, self)
				wrapped.append(arg)
			await func(WRAP[commands.Context](ctx, self), *wrapped)

		wrapper.__doc__ = func.__doc__
		wrapper.__signature__ = sig
		self._bot.command(name=func.__name__)(wrapper)

	def getChannel(self, id: str) -> IChannel:
		channel = self._bot.get_channel(int(id))
		if channel and not isinstance(channel, discord.TextChannel):
			raise ValueError("Unsupported channel")
		return Channel(channel, Guild(channel.guild))
