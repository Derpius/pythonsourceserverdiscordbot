local gm = gmod.GetGamemode()

net.Receive("Relay.NetworkMsg", function(len)
	local username  = net.ReadString()
	local message   = net.ReadString()
	local colour    = net.ReadColor()
	local role      = net.ReadString()
	local clean_msg = net.ReadString()
	if hook.Call("Relay.Message", gm, username, message, colour, role, clean_msg) ~= false then
		chat.AddText(Color(166, 157, 237), "[Relay | "..role.."] ", colour, username, Color(255, 255, 255), ": ", clean_msg)
	end
end)

net.Receive("Relay.RSay", function(len)
	local msg = net.ReadString()
	hook.Call("Relay.ConsoleMessage", gm, msg)
	chat.AddText(Color(166, 157, 237), "Console", Color(255, 255, 255), ": ", msg)
end)
