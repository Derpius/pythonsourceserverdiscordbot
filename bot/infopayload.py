from discord import Member, Role, Emoji
from typing import Dict, List, Tuple
import json

class InfoPayload:
	'''Represents the payload to be sent on valid PATCH requests'''
	def __init__(self):
		self.dirty = False # Determines if the data has been modified for calls to .encode()
		self._encoded = "" # Cached encoded data

		self.members: Dict[str, dict] = {}
		self.roles: Dict[str, dict] = {}
		self.emotes: Dict[str, tuple] = {}
	
	def updateMember(self, member: Member):
		'''Add or update a member'''
		self.dirty = True

		self.members[str(member.id)] = {
			"display-name": member.display_name,
			"username": member.name,
			"discriminator": member.discriminator,
			"avatar": str(member.avatar_url),
			"roles": [role.id for role in member.roles]
		}
	
	def removeMember(self, id: int):
		'''Remove a member from the payload'''
		self.dirty = True
		del self.members[str(id)]
	
	def setRoles(self, roles: List[Role]):
		'''Set the roles for the server'''
		self.dirty = True

		self.roles = {}
		for role in roles:
			self.roles[str(role.id)] = {
				"name": role.name,
				"colour": role.colour.to_rgb()
			}
	
	def setEmotes(self, emotes: Tuple[Emoji]):
		'''Set the emotes for the server'''
		self.dirty = True

		self.emotes = {}
		for emote in emotes: self.emotes[str(emote.id)] = {
			"name": emote.name,
			"url": str(emote.url)
		}
	
	def encode(self) -> str:
		if self.dirty:
			self._encoded = json.dumps({
				"members": self.members,
				"roles": self.roles,
				"emotes": self.emotes
			})
			self.dirty = False
		return self._encoded
