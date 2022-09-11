Relay = {}

RelayBackends = {
	Undefined = -1,
	Discord = 0,
	Revolt = 1
}
Relay.Backend = RelayBackends.Undefined

-- ConVars
if SERVER then
	Relay.RelayConnection = CreateConVar("relay_connection", "localhost:8080", FCVAR_ARCHIVE, "Connection string of the relay server (will have http:// prepended automatically)")
	Relay.RelayInterval = CreateConVar("relay_interval", 16, FCVAR_ARCHIVE, "How many ticks to wait between cache POSTs", 1)
	Relay.InfoPayloadChunkSize = CreateConVar("relay_infopayload_chunksize", 32000, FCVAR_ARCHIVE, "Size (in bytes) of each chunk when streaming the InfoPayload to clients", 1, 64000)
end

-- Shared
include("relay/infopayload/main.lua")

-- Server
if SERVER then
	print("##########################")
	print("| HTTP Chat Relay Server |")
	print("##########################")

	util.AddNetworkString("Relay.NetworkMsg")
	util.AddNetworkString("Relay.RSay")

	util.AddNetworkString("Relay.InfoPayload")
	util.AddNetworkString("Relay.InfoPayloadHeader")

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