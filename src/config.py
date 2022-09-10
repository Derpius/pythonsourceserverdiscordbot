from dataclasses import dataclass, field

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
	prefix: str = "!"
	accentColour: str = "#ffffff"
	timeDownBeforeNotify: float = 8080
	relayPort: int = 8080
	messageFormats: MessageFormats = MessageFormats()
