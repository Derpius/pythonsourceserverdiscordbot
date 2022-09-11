DiscordRelay = {}

-- ConVars
if SERVER then
	DiscordRelay.RelayConnection = CreateConVar("relay_connection", "localhost:8080", FCVAR_ARCHIVE, "Connection string of the relay server (will have http:// prepended automatically)")
	DiscordRelay.RelayInterval = CreateConVar("relay_interval", 16, FCVAR_ARCHIVE, "How many ticks to wait between cache POSTs", 1)
	DiscordRelay.InfoPayloadChunkSize = CreateConVar("relay_infopayload_chunksize", 32000, FCVAR_ARCHIVE, "Size (in bytes) of each chunk when streaming the InfoPayload to clients", 1, 64000)
end

-- Shared
include("relay/infopayload/main.lua")

-- Server
if SERVER then
	print("##########################")
	print("| HTTP Chat Relay Server |")
	print("##########################")

	util.AddNetworkString("DiscordRelay.NetworkMsg")
	util.AddNetworkString("DiscordRelay.DSay")

	util.AddNetworkString("DiscordRelay.InfoPayload")
	util.AddNetworkString("DiscordRelay.InfoPayloadHeader")

	include("relay/server.lua")
	AddCSLuaFile("relay/client.lua")

	AddCSLuaFile("relay/json.lua/json.lua")
	AddCSLuaFile("relay/infopayload/main.lua")
	AddCSLuaFile("relay/infopayload/types.lua")
	AddCSLuaFile("relay/infopayload/api.lua")
end

-- Client
if CLIENT then
	print("############################")
	print("| HTTP Chat Relay Receiver |")
	print("############################")

	include("relay/client.lua")
end