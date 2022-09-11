from .interface import Colour, IUser, IRole, IEmoji
from .config import Backend
import json

class InfoPayload:
	'''Represents the payload to be sent on valid PATCH requests'''
	def __init__(self, backend: Backend):
		self._dirty = True # Determines if the data has been modified for calls to .encode()
		self._encoded = "" # Cached encoded data

		self.members: dict[str, dict] = {}
		self.roles: dict[str, dict] = {}
		self.emojis: dict[str, dict] = {}

		self.constrs: set[str] = set()

		self.backend: Backend = backend

	def updateMember(self, member: IUser):
		'''Add or update a member'''
		self._dirty = True

		self.members[member.id] = {
			"display-name": member.displayName,
			"username": member.name,
			"avatar": member.avatar,
			"roles": [role.id for role in member.roles]
		}

	def removeMember(self, member: IUser):
		'''Remove a member from the payload'''
		self._dirty = True
		del self.members[member.id]

	def setMembers(self, members: list[IUser]):
		'''set the members for the server'''
		self._dirty = True

		self.members = {}
		for member in members: self.updateMember(member)

	def updateRole(self, role: IRole):
		'''Add or update a role'''
		self._dirty = True

		self.roles[role.id] = {
			"name": role.name,
			"colour": (role.colour.r, role.colour.g, role.colour.b) if role.colour else (255, 255, 255)
		}
	
	def removeRole(self, role: IRole):
		'''Remove a role from the payload'''
		self._dirty = True
		del self.roles[role.id]
	
	def setRoles(self, roles: list[IRole]):
		'''set the roles for the server'''
		self._dirty = True

		self.roles = {}
		for role in roles: self.updateRole(role)

	def updateEmoji(self, emoji: IEmoji):
		'''Add or update an emoji'''
		self._dirty = True

		self.emojis[emoji.id] = {
			"name": emoji.name,
			"url": emoji.url
		}

	def removeEmoji(self, emoji: IEmoji):
		'''Remove an emoji'''
		self._dirty = True
		del self.emojis[emoji.id]

	def setEmojis(self, emojis: list[IEmoji]):
		'''Set the emojis for the server'''
		self._dirty = True

		self.emojis = {}
		for emoji in emojis: self.updateEmoji(emoji)

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
				"backend": self.backend.value,
				"members": self.members,
				"roles": self.roles,
				"emotes": self.emojis
			})
			self._dirty = False
		return self._encoded
