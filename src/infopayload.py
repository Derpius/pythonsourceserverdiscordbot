from .interface import IUser, IRole, IEmoji
import json

class InfoPayload:
	'''Represents the payload to be sent on valid PATCH requests'''
	def __init__(self):
		self._dirty = False # Determines if the data has been modified for calls to .encode()
		self._encoded = "" # Cached encoded data

		self.members: dict[str, dict] = {}
		self.roles: dict[str, dict] = {}
		self.emotes: dict[str, dict] = {}

		self.constrs: set[str] = set()
	
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
			"colour": (role.colour.r, role.colour.g, role.colour.b)
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
	
	# Note that emotes have no individual events, so separate update and remove methods are pointless
	def setEmotes(self, emotes: tuple[IEmoji]):
		'''set the emotes for the server'''
		self._dirty = True

		self.emotes = {}
		for emote in emotes:
			self.emotes[emote.id] = {
				"name": emote.name,
				"url": emote.url
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
