local relayServer = "localhost:8080"

function onChat(plr, msg, teamCht)
	local plrName = plr:Nick()
	local steamID = plr:SteamID64()

	http.Fetch("http://steamcommunity.com/profiles/" .. steamID .. "?xml=1", function(content, size)
		local avatar = content:match("<avatarIcon><!%[CDATA%[(.-)%]%]></avatarIcon>")
		http.Post("http://localhost:8080", {name=plrName, message=msg, icon=avatar}, function(result)
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

	HTTP({
		failed = function(reason) print("GET Failed: " .. reason) end,
		success = httpCallback,
		method = "GET",
		url = "http://localhost:8080"
	})
end

hook.Add("PlayerSay", "relayMessagesToDiscordBot", onChat)

HTTP({
	failed = function(reason) print("GET Failed: " .. reason) end,
	success = httpCallback,
	method = "GET",
	url = "http://localhost:8080"
})