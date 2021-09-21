local string_format = string.format
local _rawget, _ipairs, _setmetatable = rawget, ipairs, setmetatable
local _error = error

/*
	InfoPayload funcs
*/
// Members
// Get the entire member table
function DiscordRelay.GetMembers()
	return {}
end
local getMembers = DiscordRelay.GetMembers

// Get a member by id
function DiscordRelay.GetMember(id)
	return nil
end
local getMember = DiscordRelay.GetMember

// Get a list of members who match the given name
function DiscordRelay.FindMembersByName(name, caseSensitive)
	if caseSensitive == nil then caseSensitive = false end

	return {}
end
local findMembersByName = DiscordRelay.FindMembersByName

// Roles
// Get the entire roles table
function DiscordRelay.GetRoles()
	return {}
end
local getRoles = DiscordRelay.GetRoles

// Get a role by id
function DiscordRelay.GetRole(id)
	return nil
end
local getRole = DiscordRelay.GetRole

// Get a list of roles that match the given name
function DiscordRelay.FindRolesByName(name, caseSensitive)
	if caseSensitive == nil then caseSensitive = false end

	return {}
end
local findRolesByName = DiscordRelay.FindRolesByName

// Emotes
// Get the entire emote table
function DiscordRelay.GetEmotes()
	return {}
end
local getEmotes = DiscordRelay.GetEmotes

// Get an emote by id
function DiscordRelay.GetEmote(id)
	return nil
end
local getEmote = DiscordRelay.GetEmote

// Get a list of emotes that match the given name
function DiscordRelay.FindEmotesByName(name, caseSensitive)
	if caseSensitive == nil then caseSensitive = false end

	return {}
end
local findEmotesByName = DiscordRelay.FindEmotesByName

/*
	Types
*/
// Member
local memberMeta = {
	__tostring = function(self)
		local roles = self:GetRoles()
		return string_format(
			"[%s] %s (%s#%s)",
			roles[#roles],
			self:GetDisplayName(),
			self:GetUsername(),
			self:GetDiscriminator()
		)
	end,
	GetId = function(self)
		return _rawget(self, "_id")
	end
	GetDisplayName = function(self)
		return _rawget(self, "_displayName")
	end,
	GetUsername = function(self)
		return _rawget(self, "_username")
	end,
	GetAvatar = function(self)
		return _rawget(self, "_avatar")
	end,
	GetDiscriminator = function(self)
		return _rawget(self, "_discrim")
	end,
	GetTag = function(self)
		return string_format("%s#%s", self:GetUsername(), self:GetDiscriminator())
	end
	GetRoles = function(self)
		local roles = {}
		for i, id in _ipairs(_rawget(self, "_roles")) do
			local role = getRole(id)
			if not role then _error(string_format("Member %i has invalid roles", self:GetId())) end
			roles[i] = role
		end
		return roles
	end,
	HasRole = function(self, id)
		if _rawget(self, "_roles")[id] then return true end
		return false
	end
}
memberMeta.__index = memberMeta

function DiscordRelay.Member(id, username, displayName, avatarUrl, discriminator, roles)
	local rolesCopy = {}
	for i, k in _ipairs(roles) do rolesCopy[i] = k end

	local member = {
		_id = id,
		_username = username,
		_displayName = displayName,
		_avatar = avatarUrl,
		_discrim = discriminator,
		_roles = rolesCopy
	}
	_setmetatable(member, memberMeta)

	return member
end
local Member = DiscordRelay.Member

// Role
local roleMeta = {
	__tostring = function(self)
		return self:GetName()
	end,
	GetId = function(self)
		return _rawget(self, "_id")
	end
	GetName = function(self)
		return _rawget(self, "_name")
	end,
	GetColour = function(self)
		return _rawget(self, "_colour")
	end,
	GetColor = function(self)
		return self:GetColour()
	end
}
roleMeta.__index = roleMeta

function DiscordRelay.Role(id, name, colour)
	local role = {
		_id = id,
		_name = name,
		_colour = colour
	}
	_setmetatable(role, roleMeta)

	return role
end
local Role = DiscordRelay.Role

// Emote
local emoteMeta = {
	__tostring = function(self)
		return string_format("<:%s:%i>", self:GetName(), self:GetId())
	end,
	GetId = function(self)
		return _rawget(self, "_id")
	end
	GetName = function(self)
		return _rawget(self, "_name")
	end,
	GetUrl = function(self)
		return _rawget(self, "_url")
	end
}
emoteMeta.__index = emoteMeta

function DiscordRelay.Emote(id, name, url)
	local emote = {
		_id = id,
		_name = name,
		_url = url
	}
	_setmetatable(emote, emoteMeta)

	return emote
end
local Emote = DiscordRelay.Emote
