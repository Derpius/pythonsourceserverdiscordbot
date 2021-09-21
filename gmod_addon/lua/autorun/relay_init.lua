DiscordRelay = {}

// ConVars
if SERVER then
	DiscordRelay.RelayConnection = CreateConVar("relay_connection", "localhost:8080", nil, "Connection string of the relay server (will have http:// prepended automatically)")
	DiscordRelay.RelayInterval = CreateConVar("relay_interval", 16, nil, "How many ticks to wait between cache POSTs", 1)
end

// Shared
include("relay/infopayload.lua")

// Server
if SERVER then
	print("##########################")
	print("| HTTP Chat Relay Server |")
	print("##########################")

	util.AddNetworkString("DiscordRelay.NetworkMsg")
	util.AddNetworkString("DiscordRelay.DSay")

	util.AddNetworkString("DiscordRelay.InfoPayload")
	util.AddNetworkString("DiscordRelay.InfoPayloadHeader")

	include("relay/relay.lua")
	AddCSLuaFile("relay/client.lua")
	AddCSLuaFile("relay/infopayload.lua")
end

// Client
if CLIENT then
	print("############################")
	print("| HTTP Chat Relay Receiver |")
	print("############################")

	include("relay/client.lua")
end