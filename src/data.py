from dataclasses import dataclass
from os import times
from typing import Dict, Iterator, List
from sourceserver.sourceserver import SourceServer
from .interface import IChannel

class Server(SourceServer):
	def __init__(self, connectionString: str, relay: bool = False, toNotify: list = []):
		super().__init__(connectionString)
		self.relay: bool = relay
		self.toNotify: List[str] = toNotify

		self.timeSinceDown: float = -1

class Servers:
	def __init__(self, json: dict) -> None:
		self._channels: Dict[str, Server] = {id: Server(data["server"], data["relay"], data["toNotify"]) for id, data in json.items()}
	
	def __iter__(self) -> Iterator[tuple[str, Server]]:
		return self._channels.items().__iter__()

	def encode(self) -> Dict[str, Server]:
		return {id: {"server": server.constr, "relay": server.relay, "toNotify": server.toNotify} for id, server in self._channels.items()}

	def channelBound(self, channel: IChannel) -> bool:
		return channel.id in self._channels

	def bindChannel(self, channel: IChannel, server: Server) -> None:
		if self.channelBound(channel): raise ValueError("Channel is already bound")
		self._channels[channel.id] = server

	def unbindChannel(self, channel: IChannel) -> None:
		if not self.channelBound(channel): raise ValueError("Channel isn't bound")
		del self._channels[channel.id]

	def __getitem__(self, channel: IChannel) -> Server:
		if not self.channelBound(channel): raise ValueError("Channel isn't bound")
		return self._channels[channel.id]
