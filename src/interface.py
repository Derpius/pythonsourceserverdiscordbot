from dataclasses import dataclass
from typing import Callable, Coroutine, Tuple
import inspect

from .config import Config

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

@dataclass
class IChannel:
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

	async def reply(self, message: str, masquerade: Masquerade | None = None) -> None:
		pass

@dataclass
class Context:
	message: IMessage

	@property
	def channel(self) -> IChannel:
		return self.message.channel

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
