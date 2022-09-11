from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Coroutine, Tuple
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
class IEmbed:
	title: str
	description: str
	icon: str
	colour: str
	url: str

@dataclass
class IUser:
	id: str
	name: str
	avatar: str
	nick: str | None

	def __str__(self) -> str:
		return self.id

	def hasPermission(self, permission: Permission) -> bool:
		pass

	async def send(self, content: str) -> None:
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

	async def send(self, message: str, masquerade: Masquerade | None = None) -> None:
		pass

@dataclass
class IMessage:
	channel: IChannel
	id: str
	author: IUser
	content: str | None
	cleanContent: str | None
	attachments: list[str]
	embeds: list[IEmbed]

	@property
	def guild(self) -> IGuild:
		return self.channel.guild

	async def reply(self, message: str, masquerade: Masquerade | None = None) -> None:
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

	async def send(self, message: str, masquerade: Masquerade | None = None) -> None:
		await self.channel.send(message, masquerade)

	async def reply(self, message: str, masquerade: Masquerade | None = None) -> None:
		await self.message.reply(message, masquerade)

class IBot:
	def __init__(self, token: str, config: Config) -> None:
		self.token = token
		self.config = config
		self.commands = {}
		self.events = {}
	
	def run(self) -> None:
		pass

	async def getChannel(self, id: str) -> IChannel:
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
