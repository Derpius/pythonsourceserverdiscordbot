from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Coroutine, List
import inspect

from .config import Config

class Permission(Enum):
	ManageGuild = auto()

@dataclass
class Masquerade:
	name: str | None = None
	avatar: str | None = None
	colour: str | None = None

@dataclass
class EmbedField:
	name: str
	value: str
	inline: bool = True

@dataclass
class Embed:
	title: str | None = None
	description: str | None = None
	icon: str | None = None
	colour: str | None = None
	url: str | None = None
	footer: str | None = None
	fields: List[EmbedField] = field(default_factory=lambda: [])

	def addField(self, name: str, value: str, inline: bool = True):
		self.fields.append(EmbedField(name, value, inline))

@dataclass
class IUser:
	id: str
	name: str
	avatar: str
	nick: str | None
	bot: bool

	@property
	def displayName(self) -> str:
		if self.nick: return self.nick
		return self.name

	def __str__(self) -> str:
		return self.id

	def hasPermission(self, permission: Permission) -> bool:
		pass

	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		pass

@dataclass
class IGuild:
	id: str
	name: str

	async def fetchMember(self, id: str) -> IUser | None:
		pass

@dataclass
class IChannel:
	guild: IGuild
	id: str
	name: str

	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		pass

@dataclass
class IMessage:
	channel: IChannel
	id: str
	author: IUser
	content: str | None
	cleanContent: str | None
	attachments: list[str]
	embeds: list[Embed]

	@property
	def guild(self) -> IGuild:
		return self.channel.guild

	async def reply(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		pass

@dataclass
class Context:
	message: IMessage

	@property
	def guild(self) -> IGuild:
		return self.message.guild

	@property
	def channel(self) -> IChannel:
		return self.message.channel

	@property
	def author(self) -> IUser:
		return self.message.author

	async def send(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		await self.channel.send(content, masquerade, embed)

	async def reply(self, content: str | None = None, masquerade: Masquerade | None = None, embed: Embed | None = None) -> None:
		await self.message.reply(content, masquerade, embed)

@dataclass
class Loop:
	interval: float
	func: Coroutine

class IBot:
	def __init__(self, token: str, config: Config) -> None:
		self.token = token
		self.config = config
		self.commands = {}
		self.events = {}
		self.loops: List[Loop] = []
	
	async def start(self) -> None:
		pass

	async def waitUntilReady(self) -> None:
		pass

	def getChannel(self, id: str) -> IChannel:
		pass

	def command(self, func: Coroutine) -> None:
		if func.__name__ in self.commands: raise ValueError("Command already registered")
		self.commands[func.__name__] = {
			"func": func,
			"help": func.__doc__
		}
	
	def event(self, func: Coroutine) -> None:
		if func.__name__ in self.events: raise ValueError("Event already registered")
		self.events[func.__name__] = func
	
	def loop(self, interval: float) -> None:
		def decorator(func: Coroutine) -> None:
			self.loops.append(Loop(interval, func))
		return decorator
