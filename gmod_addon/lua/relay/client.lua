net.Receive("DiscordRelay.NetworkMsg", function(len)
	local username = net.ReadString()
	local message = net.ReadString()
	local colour = net.ReadColor()
	local role = net.ReadString()

	chat.AddText(Color(166, 157, 237), "[Discord | "..role.."] ", colour, username, Color(255, 255, 255), ": ", message)
	hook.Run("DiscordRelay.Message", username, message, colour, role)
end)