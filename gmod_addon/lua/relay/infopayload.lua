local members, roles, emotes = {}, {}, {}
local relay_connection = GetConVar("relay_connection")
local hostport = GetConVar("hostport")

local string_format, string_find, string_lower, string_sub = string.format, string.find, string.lower, string.sub
local _rawget, _setmetatable = rawget, setmetatable
local _ipairs, _pairs = ipairs, pairs
local _error = error
local _tonumber = tonumber

local table_insert, table_sort, table_concat = table.insert, table.sort, table.concat

local util_JSONToTable, util_TableToJSON = util.JSONToTable, util.TableToJSON
local util_Compress, util_Decompress = util.Compress, util.Decompress
local util_CRC = util.CRC

local net_Start, net_Receive = net.Start, net.Receive
local net_WriteData, net_ReadData = net.WriteData, net.ReadData
local net_WriteUInt, net_ReadUInt = net.WriteUInt, net.ReadUInt
local net_Broadcast, net_SendToServer, net_Send = net.Broadcast, net.SendToServer, net.Send

local _HTTP = HTTP

local math_ceil = math.ceil

/*
	Netcode
*/
local function decodePayload(payload)
	members, roles, emotes = {}, {}, {}
	for id, member in _pairs(payload.members) do
		id = _tonumber(id)
		members[id] = Member(id, member.username, member["display-name"], member.avatar, member.discriminator, member.roles)
	end

	for id, role in _pairs(payload.roles) do
		id = _tonumber(id)
		roles[id] = Role(id, role.name, Color(role.colour[1], role.colour[2], role.colour[3]))
	end

	for id, emote in _pairs(payload.emotes) do
		id = _tonumber(id)
		emotes[id] = Emote(id, emote.name, emote.url)
	end
end

if SERVER then
	local chunkSize = 32000

	local function stream(data, plr)
		// Send header
		net_Start("DiscordRelay.InfoPayloadHeader")
		net_WriteUInt(math_ceil(#data / chunkSize), 32)
		if plr then
			net_Send(plr)
		else
			net_Broadcast()
		end

		local id = 1
		for i = 1, #data, chunkSize do
			local packet = string_sub(data, i, i + chunkSize - 1)

			// Send packet
			net_Start("DiscordRelay.InfoPayload")
			net_WriteUInt(id, 32)
			net_WriteData(packet)
			if plr then
				net_Send(plr)
			else
				net_Broadcast()
			end

			id = id + 1
		end
	end

	function DiscordRelay.UpdateInfo()
		_HTTP({
			success = function(statusCode, content, headers)
				if statusCode != 200 then return end

				// Stream payload to clients
				stream(util_Compress(content))

				// Decode
				decodePayload(util_JSONToTable(content))
			end,
			method = "PATCH",
			url = "http://"..relay_connection:GetString(),
			headers = {["Source-Port"] = hostport:GetString()}
		})
	end

	// Clients will send this whenever they init to request the server's data
	net_Receive("DiscordRelay.InfoPayload", function(len, plr)
		stream(util_Compress(util_TableToJSON({
			members = members,
			roles = roles,
			emotes = emotes
		})), plr)
	end)
else
	local streamBuffer, streamLength, streamToReceive = {}, 0, 0
	net_Receive("DiscordRelay.InfoPayloadHeader", function()
		print("Header received")
		streamBuffer = {}
		streamLength = net_ReadUInt(32)
		streamToReceive = streamLength
	end)

	net_Receive("DiscordRelay.InfoPayload", function(len)
		print("Packet received")
		if streamToReceive == 0 then return end // If this client isn't expecting a packet, drop it
		print("Packet valid")

		local id = net_ReadUInt(32)
		local packet = net_ReadData((len - 32) / 8)

		streamBuffer[id] = packet
		streamToReceive = streamToReceive - 1

		print(string.format("Buffered packet %i", id))
		PrintTable(streamBuffer)

		if streamToReceive == 0 then
			local payload = table_concat(streamBuffer, "", 1, streamLength)
			payload = util_JSONToTable(util_Decompress(payload))

			decodePayload(payload)
		end
	end)

	// Let the server know we're a new client and should be given a copy of the info payload
	hook.Add("InitPostEntity", "DiscordRelay.InfoPayloadClientInit", function()
		net_Start("DiscordRelay.InfoPayload")
		net_SendToServer()
	end)
end

/*
	InfoPayload funcs
*/
local function sortedFind(tbl, match)
	// Get matches
	local matches = {}
	for k, v in _pairs(tbl) do
		local weight = match(v)
		if weight then table_insert(matches, {weight, v}) end
	end

	// Sort
	table_sort(matches, function(a, b) return a[1] < b[1] end)

	// Clean table
	for i, v in _ipairs(matches) do matches[i] = matches[i][2] end

	return matches
end

// Members
// Get the entire member table
function DiscordRelay.GetMembers()
	return members
end
local getMembers = DiscordRelay.GetMembers

// Get a member by id
function DiscordRelay.GetMember(id)
	return members[id]
end
local getMember = DiscordRelay.GetMember

// Get a list of members who match the given name (sorted by importance descending)
function DiscordRelay.FindMembersByName(name, caseSensitive)
	if caseSensitive == nil then caseSensitive = false end
	if not caseSensitive then name = string_lower(name) end

	return sortedFind(members, function(member)
		local matchIdx = string_find(
			caseSensitive and member:GetDisplayName() or string_lower(member:GetDisplayName()),
			name
		)

		if not matchIdx then
			matchIdx = string_find(
				caseSensitive and member:GetUsername() or string_lower(member:GetUsername()),
				name
			)

			if matchIdx then
				return matchIdx * 10 // Heavily weight only username matches to the end
			end
		end

		return matchIdx
	end)
end
local findMembersByName = DiscordRelay.FindMembersByName

// Roles
// Get the entire roles table
function DiscordRelay.GetRoles()
	return roles
end
local getRoles = DiscordRelay.GetRoles

// Get a role by id
function DiscordRelay.GetRole(id)
	return roles[id]
end
local getRole = DiscordRelay.GetRole

// Get a list of roles that match the given name (sorted by importance descending)
function DiscordRelay.FindRolesByName(name, caseSensitive)
	if caseSensitive == nil then caseSensitive = false end
	if not caseSensitive then name = string_lower(name) end

	return sortedFind(roles, function(role)
		return string_find(
			caseSensitive and role:GetName() or string_lower(role:GetName()),
			name
		)
	end)
end
local findRolesByName = DiscordRelay.FindRolesByName

// Emotes
// Get the entire emote table
function DiscordRelay.GetEmotes()
	return emotes
end
local getEmotes = DiscordRelay.GetEmotes

// Get an emote by id
function DiscordRelay.GetEmote(id)
	return emotes[id]
end
local getEmote = DiscordRelay.GetEmote

// Get a list of emotes that match the given name (sorted by importance descending)
function DiscordRelay.FindEmotesByName(name, caseSensitive)
	if caseSensitive == nil then caseSensitive = false end
	if not caseSensitive then name = string_lower(name) end

	return sortedFind(emotes, function(emote)
		return string_find(
			caseSensitive and emote:GetName() or string_lower(emote:GetName()),
			name
		)
	end)
end
local findEmotesByName = DiscordRelay.FindEmotesByName

/*
	Types
*/
// Member
local memberMeta = {}
function memberMeta:__tostring()
	local roles = self:GetRoles()
	return string_format(
		"[%s] %s (%s#%s)",
		roles[#roles],
		self:GetDisplayName(),
		self:GetUsername(),
		self:GetDiscriminator()
	)
end
function memberMeta:GetId()
	return _rawget(self, "_id")
end
function memberMeta:GetDisplayName()
	return _rawget(self, "_displayName")
end
function memberMeta:GetUsername()
	return _rawget(self, "_username")
end
function memberMeta:GetAvatar()
	return _rawget(self, "_avatar")
end
function memberMeta:GetDiscriminator()
	return _rawget(self, "_discrim")
end
function memberMeta:GetTag()
	return string_format("%s#%s", self:GetUsername(), self:GetDiscriminator())
end
function memberMeta:GetRoles()
	local roles = {}
	for i, id in _ipairs(_rawget(self, "_roles")) do
		local role = getRole(id)
		if not role then _error(string_format("Member %i has invalid roles", self:GetId())) end
		roles[i] = role
	end
	return roles
end
function memberMeta:HasRole(id)
	if _rawget(self, "_roles")[id] then return true end
	return false
end
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
local roleMeta = {}
function roleMeta:__tostring()
	return self:GetName()
end
function roleMeta:GetId()
	return _rawget(self, "_id")
end
function roleMeta:GetName()
	return _rawget(self, "_name")
end
function roleMeta:GetColour()
	return _rawget(self, "_colour")
end
function roleMeta:GetColor()
	return self:GetColour()
end
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
local emoteMeta = {}
function emoteMeta:__tostring()
	return string_format("<:%s:%i>", self:GetName(), self:GetId())
end
function emoteMeta:GetId()
	return _rawget(self, "_id")
end
function emoteMeta:GetName()
	return _rawget(self, "_name")
end
function emoteMeta:GetUrl()
	return _rawget(self, "_url")
end
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
