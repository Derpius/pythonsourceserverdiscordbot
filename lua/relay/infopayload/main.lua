local members, roles, emotes = {}, {}, {}
local relay_connection, relay_infopayload_chunksize = Relay.RelayConnection, Relay.InfoPayloadChunkSize
local hostport = GetConVar("hostport")

local string_find, string_lower, string_sub = string.find, string.lower, string.sub
local _pairs, _error = pairs, error

local table_concat = table.concat

local util_Compress, util_Decompress = util.Compress, util.Decompress

local net_Start, net_Receive = net.Start, net.Receive
local net_WriteData, net_ReadData = net.WriteData, net.ReadData
local net_WriteUInt, net_ReadUInt = net.WriteUInt, net.ReadUInt
local net_Broadcast, net_SendToServer, net_Send = net.Broadcast, net.SendToServer, net.Send

local _HTTP = HTTP

local math_ceil = math.ceil

local apiRefTbl = include("api.lua")
local Member, Role, Emote = include("types.lua")
local json = include("relay/json.lua/json.lua")

local gm = gmod.GetGamemode()

--[[
	Netcode
]]
local function decodePayload(payload)
	Relay.Backend = payload.backend

	members, roles, emotes = {}, {}, {}
	for id, member in _pairs(payload.members) do
		members[id] = Member(id, member.username, member["display-name"], member.avatar, member.roles)
	end

	for id, role in _pairs(payload.roles) do
		roles[id] = Role(id, role.name, Color(role.colour[1], role.colour[2], role.colour[3]))
	end

	for id, emote in _pairs(payload.emotes) do
		emotes[id] = Emote(id, emote.name, emote.url)
	end

	apiRefTbl.members = members
	apiRefTbl.roles = roles
	apiRefTbl.emotes = emotes

	hook.Call("Relay.InfoPayloadUpdated", gm)
end

if SERVER then
	local function stream(data, plr)
		local chunkSize = relay_infopayload_chunksize:GetInt()
		if chunkSize == 0 or not chunkSize then
			_error("Invalid chunk size (change relay_infopayload_chunksize convar)")
		end

		-- Send header
		net_Start("Relay.InfoPayloadHeader")
		net_WriteUInt(math_ceil(#data / chunkSize), 32)
		if plr then
			net_Send(plr)
		else
			net_Broadcast()
		end

		local id = 1
		for i = 1, #data, chunkSize do
			local packet = string_sub(data, i, i + chunkSize - 1)

			-- Send packet
			net_Start("Relay.InfoPayload")
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

	local rawPayload = ""
	function Relay.UpdateInfo()
		_HTTP({
			success = function(statusCode, content, headers)
				if statusCode ~= 200 then
					return
				end

				-- Stream payload to clients
				rawPayload = util_Compress(content)
				stream(rawPayload)

				-- Decode
				decodePayload(json.decode(content))
			end,
			method = "PATCH",
			url = "http://" .. relay_connection:GetString(),
			headers = { ["Source-Port"] = hostport:GetString() },
		})
	end

	-- Clients will send this whenever they init to request the server's data
	net_Receive("Relay.InfoPayload", function(len, plr)
		stream(rawPayload, plr)
	end)
else
	local streamBuffer, streamLength, streamToReceive = {}, 0, 0
	net_Receive("Relay.InfoPayloadHeader", function()
		streamBuffer = {}
		streamLength = net_ReadUInt(32)
		streamToReceive = streamLength
	end)

	net_Receive("Relay.InfoPayload", function(len)
		if streamToReceive == 0 then
			return
		end -- If this client isn't expecting a packet, drop it

		local id = net_ReadUInt(32)
		local packet = net_ReadData((len - 32) / 8)

		streamBuffer[id] = packet
		streamToReceive = streamToReceive - 1

		if streamToReceive == 0 then
			local payload = table_concat(streamBuffer, "", 1, streamLength)
			payload = json.decode(util_Decompress(payload))

			decodePayload(payload)
		end
	end)

	-- Let the server know we're a new client and should be given a copy of the info payload
	hook.Add("InitPostEntity", "Relay.InfoPayloadClientInit", function()
		net_Start("Relay.InfoPayload")
		net_SendToServer()
	end)
end
