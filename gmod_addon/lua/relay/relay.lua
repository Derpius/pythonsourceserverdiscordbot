local toggle = false

function onChat(plr, msg, teamCht)
	if not toggle then return end
	local plrName = plr:Nick()
	local steamID = plr:SteamID64()
	local teamID = plr:Team()

	http.Fetch("http://steamcommunity.com/profiles/" .. steamID .. "?xml=1", function(content, size)
		local avatar = content:match("<avatarIcon><!%[CDATA%[(.-)%]%]></avatarIcon>")
		http.Post("http://" .. connection, {name=plrName, message=msg, icon=avatar, teamName=team.GetName(teamID)}, function(result)
			if result then print("Message POSTed to bot") end
		end, function(failed)
			print(failed)
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

hook.Add("PlayerSay", "relayMessagesToDiscordBot", onChat)

concommand.Add("startRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() then
		toggle = true

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
		print("Relay stopped")
	end
end)