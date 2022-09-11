local string_format = string.format
local _setmetatable = setmetatable
local _ipairs = ipairs
local _error = error

local getRole = Relay.GetRole

-- Member
local memberMeta = {}
function memberMeta:__tostring()
	return ({
		[RelayBackends.Undefined] = self:GetDisplayName(),
		[RelayBackends.Discord] = string_format("<@%s>", self:GetId()),
		[RelayBackends.Revolt] = string_format("<@%s>", self:GetId())
	})[Relay.Backend]
end

function memberMeta:GetId()
	return self._id
end

function memberMeta:GetDisplayName()
	return self._displayName
end

function memberMeta:GetUsername()
	return self._username
end

function memberMeta:GetAvatar()
	return self._avatar
end

function memberMeta:GetRoles()
	local roles = {}
	for i, id in _ipairs(self._roles) do
		local role = getRole(id)
		if not role then _error(string_format("Member %s has invalid roles", self:GetId())) end
		roles[i] = role
	end
	return roles
end

function memberMeta:HasRole(matchId)
	for _, id in ipairs(self._roles) do
		if id == matchId then return true end
	end

	return false
end

function memberMeta:GetTopRole()
	return getRole(self._roles[self._numRoles])
end

function memberMeta:GetColour()
	return self:GetTopRole():GetColour()
end
memberMeta.GetColor = memberMeta.GetColour

memberMeta.__name = "Member"
memberMeta.__index = memberMeta

function Relay.Member(id, username, displayName, avatarUrl, roles)
	local rolesCopy = {}
	for i, k in _ipairs(roles) do rolesCopy[i] = k end

	local member = {
		_id = id,
		_username = username,
		_displayName = displayName,
		_avatar = avatarUrl,
		_roles = rolesCopy,
		_numRoles = #rolesCopy
	}
	_setmetatable(member, memberMeta)

	return member
end

-- Role
local roleMeta = {}
function roleMeta:__tostring()
	return ({
		[RelayBackends.Undefined] = self:GetName(),
		[RelayBackends.Discord] = string_format("<@&%s>", self:GetId()),
		[RelayBackends.Revolt] = self:GetName()
	})[Relay.Backend]
end

function roleMeta:GetId()
	return self._id
end

function roleMeta:GetName()
	return self._name
end

function roleMeta:GetColour()
	return self._colour
end
roleMeta.GetColor = roleMeta.GetColour

roleMeta.__name = "Role"
roleMeta.__index = roleMeta

function Relay.Role(id, name, colour)
	local role = {
		_id = id,
		_name = name,
		_colour = colour
	}
	_setmetatable(role, roleMeta)

	return role
end

-- Emote
local emoteMeta = {}
function emoteMeta:__tostring()
	return ({
		[RelayBackends.Undefined] = self:GetName(),
		[RelayBackends.Discord] = string_format("<:%s:%s>", self:GetName(), self:GetId()),
		[RelayBackends.Revolt] = string_format(":%s:", self:GetId())
	})[Relay.Backend]
end

function emoteMeta:GetId()
	return self._id
end

function emoteMeta:GetName()
	return self._name
end

function emoteMeta:GetUrl()
	return self._url
end

emoteMeta.__name = "Emote"
emoteMeta.__index = emoteMeta

function Relay.Emote(id, name, url)
	local emote = {
		_id = id,
		_name = name,
		_url = url
	}
	_setmetatable(emote, emoteMeta)

	return emote
end

return Relay.Member, Relay.Role, Relay.Emote
