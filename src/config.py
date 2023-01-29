from dataclasses import dataclass, field
from enum import Enum
from .utils import Colour

class Backend(Enum):
	Undefined = -1,
	Discord = 0,
	Revolt = 1

BACKENDS = {
	"discord": Backend.Discord,
	"revolt": Backend.Revolt
}

@dataclass
class MessageFormats:
	join: list[str] = field(default_factory=lambda: ["`{player}` just joined the server!"])
	leave: list[str] = field(default_factory=lambda: ["`{player}` just left the server"])
	suicide: list[str] = field(default_factory=lambda: ["`{victim}` killed themselves with `{inflictor}`"])
	suicideNoWeapon: list[str] = field(default_factory=lambda: ["`{victim}` killed themselves"])
	kill: list[str] = field(default_factory=lambda: ["`{attacker}` killed `{victim}` with `{inflictor}`"])
	killNoWeapon: list[str] = field(default_factory=lambda: ["`{attacker}` killed `{victim}`"])

@dataclass
class Config:
	backend: Backend = Backend.Undefined
	prefix: str = "!"
	accentColour: Colour = field(default_factory=lambda: Colour(255, 255, 255))
	timeDownBeforeNotify: float = 8080
	relayPort: int = 8080
	messageFormats: MessageFormats = MessageFormats()

	@staticmethod
	def fromJSON(config: dict):
		return Config(
			BACKENDS[config["backend"]] if config["backend"] in BACKENDS else Backend.Undefined,
			config["prefix"], Colour(config["accent-colour"][0], config["accent-colour"][1], config["accent-colour"][2]),
			config["time-down-before-notify"],
			config["relay-port"],
			MessageFormats(
				config["message-formats"]["join"], config["message-formats"]["leave"],
				config["message-formats"]["suicide"], config["message-formats"]["suicide-no-weapon"],
				config["message-formats"]["kill"], config["message-formats"]["kill-no-weapon"]
			)
		)
