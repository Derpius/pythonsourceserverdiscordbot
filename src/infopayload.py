from discord import Member, Role, Emoji
from typing import Dict, List, Tuple, Set
import json

class InfoPayload:
	'''Represents the payload to be sent on valid PATCH requests'''
	def __init__(self):
		self._dirty = False # Determines if the data has been modified for calls to .encode()
		self._encoded = "" # Cached encoded data

		self.members: Dict[str, dict] = {}
		self.roles: Dict[str, dict] = {}
		self.emotes: Dict[str, tuple] = {}

		self.constrs: Set[str] = set()
	
	def updateMember(self, member: Member):
		'''Add or update a member'''
		self._dirty = True

		self.members[str(member.id)] = {
			"display-name": member.display_name,
			"username": member.name,
			"discriminator": member.discriminator,
			"avatar": str(member.avatar_url),
			"roles": [str(role.id) for role in member.roles]
		}
	
	def removeMember(self, member: Member):
		'''Remove a member from the payload'''
		self._dirty = True
		del self.members[str(member.id)]
	
	def setMembers(self, members: List[Member]):
		'''Set the members for the server'''
		self._dirty = True

		self.members = {}
		for member in members: self.updateMember(member)
	
	def updateRole(self, role: Role):
		'''Add or update a role'''
		self._dirty = True

		self.roles[str(role.id)] = {
			"name": role.name,
			"colour": role.colour.to_rgb()
		}
	
	def removeRole(self, role: Role):
		'''Remove a role from the payload'''
		self._dirty = True
		del self.roles[str(role.id)]
	
	def setRoles(self, roles: List[Role]):
		'''Set the roles for the server'''
		self._dirty = True

		self.roles = {}
		for role in roles: self.updateRole(role)
	
	# Note that emotes have no individual events, so separate update and remove methods are pointless
	def setEmotes(self, emotes: Tuple[Emoji]):
		'''Set the emotes for the server'''
		self._dirty = True

		self.emotes = {}
		for emote in emotes:
			self.emotes[str(emote.id)] = {
				"name": emote.name,
				"url": str(emote.url)
			}
	
	def addConStr(self, constr: str):
		'''Add a connection string that this info payload is being used with'''
		self.constrs.add(constr)
	
	def removeConStr(self, constr: str):
		'''Remove a connection string that this info payload was being used with'''
		self.constrs.remove(constr)
	
	def encode(self) -> str:
		'''Encode the payload as JSON (caches the result for later)'''
		if self._dirty:
			self._encoded = json.dumps({
				"members": self.members,
				"roles": self.roles,
				"emotes": self.emotes
			})
			self._dirty = False
		return self._encoded
