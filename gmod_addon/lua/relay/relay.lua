local toggle = false

function onJoinOrLeave(plrNick, reqType)
	http.Post("http://" .. connection, {type=reqType, name=plrNick}, function(result)
		if result then print("Join/Leave event POSTed to bot") end
	end, function(reason)
		print("Join/Leave POST failed: ".. reason)
	end)
end

function onChat(plr, msg, teamCht)
	http.Fetch("http://steamcommunity.com/profiles/" .. plr:SteamID64() .. "?xml=1", function(content, size)
		local avatar = content:match("<avatarIcon><!%[CDATA%[(.-)%]%]></avatarIcon>")
		http.Post("http://" .. connection, {type="message", name=plr:Nick(), message=msg, icon=avatar, teamName=team.GetName(plr:Team())}, function(result)
			if result then print("Message POSTed to bot") end
		end, function(reason)
			print("Message POST failed: ".. reason)
		end)
	end)
end

function httpCallback(statusCode, content, headers)
	if statusCode != 200 then
		print("GET failed with status code " .. tostring(statusCode))
	end

	if content != "none" then
		JSON = util.JSONToTable(content)

		for _, msg in pairs(JSON) do
			print("[Discord] " .. msg[1] .. ": " .. msg[2])
			local colour = Color(msg[3][1], msg[3][2], msg[3][3])

			net.Start("relayDiscordMessageReceived")
				net.WriteString(msg[1])
				net.WriteString(msg[2])
				net.WriteColor(colour)
				hook.Run("GModRelay.DiscordMsg", msg[1], msg[2])
			net.Broadcast()
		end
	end

	if toggle then
		HTTP({
			failed = function(reason) print("GET Failed: " .. reason) end,
			success = httpCallback,
			method = "GET",
			url = "http://" .. connection
		})
	end
end

concommand.Add("startRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() then
		toggle = true

		hook.Add("PlayerSay", "relayMessagesToDiscordBot", onChat)
		hook.Add("PlayerInitialSpawn", "relayJoinsToDiscordBot", function(plr) onJoinOrLeave(plr:Nick(), "join") end)
		hook.Add("PlayerDisconnected", "relayLeavesToDiscordBot", function(plr) onJoinOrLeave(plr:Nick(), "leave") end)

		HTTP({
			failed = function(reason) print("GET Failed: " .. reason) end,
			success = httpCallback,
			method = "GET",
			url = "http://" .. connection
		})

		print("Relay started")
	end
end)
concommand.Add("stopRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() then
		toggle = false

		hook.Remove("PlayerSay", "relayMessagesToDiscordBot")
		hook.Remove("PlayerInitialSpawn", "relayJoinsToDiscordBot")
		hook.Remove("PlayerDisconnected", "relayLeavesToDiscordBot")

		print("Relay stopped")
	end
end)