local toggle = false

function onJoinOrLeave(plrNick, reqType)
	http.Post("http://" .. connection, {type=reqType, name=plrNick}, function(result)
		if result then print("Join/Leave event POSTed to bot") end
	end, function(reason)
		print("Join/Leave POST failed: "..reason)
	end)
end

function onChat(plr, msg, teamCht)
	http.Fetch("http://steamcommunity.com/profiles/" .. plr:SteamID64() .. "?xml=1", function(content, size)
		local avatar = content:match("<avatarIcon><!%[CDATA%[(.-)%]%]></avatarIcon>") or ""
		local teamColour = team.GetColor(plr:Team())
		http.Post("http://" .. connection, {
			type="message",
			name=plr:Nick(), message=msg, icon=avatar,
			teamName=team.GetName(plr:Team()), teamColour=tostring(teamColour.r)..","..tostring(teamColour.g)..","..tostring(teamColour.b),
			steamID = plr:SteamID()
		}, function(result)
			if verbose and result then print("Message POSTed to bot") end
		end, function(reason)
			if verbose then print("Message POST failed: "..reason) end
		end)
	end)
end

function httpCallback(statusCode, content, headers)
	if statusCode != 200 then
		if verbose then print("GET failed with status code " .. tostring(statusCode)) end
	elseif content != "none" then
		JSON = util.JSONToTable(content)

		for _, msg in pairs(JSON) do
			print("[Discord | "..msg[4].."] " .. msg[1] .. ": " .. msg[2])
			local colour = Color(msg[3][1], msg[3][2], msg[3][3])

			net.Start("relayDiscordMessageReceived")
				net.WriteString(msg[1])
				net.WriteString(msg[2])
				net.WriteColor(colour)
				net.WriteString(msg[4])
				hook.Run("GModRelay.DiscordMsg", msg[1], msg[2], colour, msg[4])
			net.Broadcast()
		end
	end

	if toggle then
		HTTP({
			failed = function() httpCallback(500, "none") end,
			success = httpCallback,
			method = "GET",
			url = "http://" .. connection
		})
	end
end

concommand.Add("startRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() then
		toggle = true
		http.Post("http://" .. connection, {type="custom", body="Relay client connected!"}, function(result)
			if verbose and result then print("Connection message POSTed to bot") end
		end, function(reason)
			if verbose then print("Connection message POST failed: "..reason) end
		end)

		hook.Add("PlayerSay", "relayMessagesToDiscordBot", onChat)
		hook.Add("PlayerInitialSpawn", "relayJoinsToDiscordBot", function(plr) onJoinOrLeave(plr:Nick(), "join") end)
		hook.Add("PlayerDisconnected", "relayLeavesToDiscordBot", function(plr) onJoinOrLeave(plr:Nick(), "leave") end)
		hook.Add("PlayerDeath", "relayDeathsToDiscordBot", function(vic, inf, atk)
			http.Post("http://" .. connection, {
				type="death",
				victim=vic:Name(), inflictor=inf.Name and inf:Name() or inf:GetClass(), attacker=atk.Name and atk:Name() or atk:GetClass(),
				suicide=vic == atk and "1" or "0", noweapon=inf:GetClass() == atk:GetClass() and "1" or "0"
			}, function(result)
				if verbose and result then print("Death POSTed to bot") end
			end, function(reason)
				if verbose then print("Death POST failed: "..reason) end
			end)
		end)

		hook.Add("PlayerDeath", "hookTest", function(vic, inf, atk) print(vic:Name(), inf.Name and inf:Name() or inf:GetClass(), atk.Name and atk:Name() or atk:GetClass()) end)

		HTTP({
			failed = function() httpCallback(500, "none") end,
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
		http.Post("http://" .. connection, {type="custom", body="Relay client disconnected"}, function(result)
			if verbose and result then print("Disconnect message POSTed to bot") end
		end, function(reason)
			if verbose then print("Disconnect message POST failed: "..reason) end
		end)

		hook.Remove("PlayerSay", "relayMessagesToDiscordBot")
		hook.Remove("PlayerInitialSpawn", "relayJoinsToDiscordBot")
		hook.Remove("PlayerDisconnected", "relayLeavesToDiscordBot")
		hook.Remove("PlayerDeath", "relayDeathsToDiscordBot")

		print("Relay stopped")
	end
end)