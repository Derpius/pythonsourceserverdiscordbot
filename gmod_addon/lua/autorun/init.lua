if SERVER then
	print("##########################")
	print("| HTTP Chat Relay Server |")
	print("##########################")

	util.AddNetworkString("relayDiscordMessageReceived")

	local connection = "localhost:8080"

	include("relay/relay.lua")
	AddCSLuaFile("relay/client.lua")
end

if CLIENT then
	print("############################")
	print("| HTTP Chat Relay Receiver |")
	print("############################")

	include("relay/client.lua")
end