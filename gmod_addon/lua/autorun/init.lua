if SERVER then
	print("##########################")
	print("| HTTP Chat Relay Server |")
	print("##########################")

	util.AddNetworkString("relayDiscordMessageReceived")

	connection = "192.168.0.97:8080"
	verbose = false

	include("relay/relay.lua")
	AddCSLuaFile("relay/client.lua")
end

if CLIENT then
	print("############################")
	print("| HTTP Chat Relay Receiver |")
	print("############################")

	include("relay/client.lua")
end