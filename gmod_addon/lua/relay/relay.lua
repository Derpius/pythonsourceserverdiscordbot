local sv_hibernate_think = GetConVar("sv_hibernate_think")
local relay_connection, relay_postinterval = GetConVar("relay_connection"), GetConVar("relay_postinterval")

local toggle = false

local toPost = {}
local tickTimer = 0



local function cachePost(body)
	local nonce = 1
	local key = tostring(math.floor(CurTime()))..string.char(nonce)

	while toPost[key] do
		key = string.SetChar(key, #key, string.char(nonce))
		nonce = nonce + 1
		if nonce > 255 then
			print("More than 255 messages in a single second, preventing caching more to avoid issues")
			return
		end
	end

	toPost[key] = body
end

local function onChat(plr, msg, teamCht)
	local teamColour = team.GetColor(plr:Team())
	cachePost({
		type="message",
		name=plr:Nick(), message=msg,
		teamName=team.GetName(plr:Team()), teamColour=tostring(teamColour.r)..","..tostring(teamColour.g)..","..tostring(teamColour.b),
		steamID = plr:SteamID64()
	})
end

local function httpCallbackError(reason)
	print("GET failed with reason: "..reason)

	if toggle then
		HTTP({
			failed = function(reason) timer.Simple(0, function() httpCallbackError(reason) end) end,
			success = httpCallback,
			method = "GET",
			url = "http://"..relay_connection:GetString()
		})
	end
end

local function httpCallback(statusCode, content, headers)
	if statusCode != 200 then
		print("GET failed with status code "..tostring(statusCode))
	elseif content != "none" then
		JSON = util.JSONToTable(content)

		for _, msg in pairs(JSON) do
			print("[Discord | "..msg[4].."] " .. msg[1] .. ": " .. msg[2])
			local colour = Color(msg[3][1], msg[3][2], msg[3][3])

			net.Start("DiscordRelay.NetworkMsg")
				net.WriteString(msg[1])
				net.WriteString(msg[2])
				net.WriteColor(colour)
				net.WriteString(msg[4])
				hook.Run("DiscordRelay.Message", msg[1], msg[2], colour, msg[4])
			net.Broadcast()
		end
	end

	if toggle then
		HTTP({
			failed = function(reason) timer.Simple(0, function() httpCallbackError(reason) end) end,
			success = httpCallback,
			method = "GET",
			url = "http://"..relay_connection:GetString()
		})
	end
end

concommand.Add("startRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() and not toggle then
		toggle = true

		hook.Add("PlayerSay", "DiscordRelay.CacheChat", onChat)
		hook.Add("PlayerInitialSpawn", "DiscordRelay.CacheJoins", function(plr) cachePost({type="join", name=plr:Nick()}) end)
		hook.Add("PlayerDisconnected", "DiscordRelay.CacheLeaves", function(plr)
			cachePost({type="leave", name=plr:Nick()})

			-- Edge case: if this leave event caused the server to go into hibernation, manually post the cache now
			if not sv_hibernate_think:GetBool() and player.GetCount() == 1 then
				HTTP({
					method = "POST",
					url = "http://"..relay_connection:GetString(),
					body = util.TableToJSON(toPost),
					type = "application/json"
				})
				toPost = {}
			end
		end)
		hook.Add("PlayerDeath", "DiscordRelay.CacheDeaths", function(vic, inf, atk)
			cachePost({
				type="death",
				victim=vic:Name(), inflictor=inf.Name and inf:Name() or inf:GetClass(), attacker=atk.Name and atk:Name() or atk:GetClass(),
				suicide=vic == atk and "1" or "0", noweapon=inf:GetClass() == atk:GetClass() and "1" or "0"
			})
		end)

		HTTP({
			failed = function(reason) timer.Simple(0, function() httpCallbackError(reason) end) end,
			success = httpCallback,
			method = "GET",
			url = "http://"..relay_connection:GetString()
		})

		hook.Add("Tick", "DiscordRelay.Post", function()
			tickTimer = (tickTimer + 1) % relay_postinterval:GetInt()
			if tickTimer ~= 0 or #table.GetKeys(toPost) == 0 then return end

			HTTP({
				method = "POST",
				url = "http://"..relay_connection:GetString(),
				body = util.TableToJSON(toPost),
				type = "application/json"
			})
			toPost = {}
		end)

		print("Relay started")
		HTTP({
			method = "POST",
			url = "http://"..relay_connection:GetString(),
			body = '{"0":{"type":"custom","body":"Relay client connected!"}}',
			type = "application/json"
		})
	end
end)
concommand.Add("stopRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() and toggle then
		toggle = false

		hook.Remove("PlayerSay", "DiscordRelay.CacheChat")
		hook.Remove("PlayerInitialSpawn", "DiscordRelay.CacheJoins")
		hook.Remove("PlayerDisconnected", "DiscordRelay.CacheLeaves")
		hook.Remove("PlayerDeath", "DiscordRelay.CacheDeaths")

		hook.Remove("Tick", "DiscordRelay.Post")

		print("Relay stopped")
		cachePost({type="custom", body="Relay client disconnected"})

		-- POST any remaining messages including the disconnect one
		HTTP({
			method = "POST",
			url = "http://"..relay_connection:GetString(),
			body = util.TableToJSON(toPost),
			type = "application/json"
		})
		toPost = {}
	end
end)

concommand.Add("dsay", function(plr, cmd, args, argStr)
	if plr:IsPlayer() then print("Only the server can use this command") end
	if not toggle then print("Please start the relay with startRelay first"); return end

	cachePost({type="custom", body="[CONSOLE]: "..argStr})
	RunConsoleCommand("say", argStr)

	-- If the server is hibernating then manually POST
	if not sv_hibernate_think:GetBool() and player.GetCount() == 0 then
		HTTP({
			method = "POST",
			url = "http://"..relay_connection:GetString(),
			body = util.TableToJSON(toPost),
			type = "application/json"
		})
		toPost = {}
	end
end, nil, "Same as say except sends to Discord too")