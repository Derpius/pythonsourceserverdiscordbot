local connection = "localhost:8080"
local verbose = false
local toggle = false

local postInterval = 16 -- how often to check for messages to post (ticks)
local toPost = {}

local tickTimer = 0

local sv_hibernate_think = GetConVar("sv_hibernate_think")

function cachePost(body)
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

function onChat(plr, msg, teamCht)
	local teamColour = team.GetColor(plr:Team())
	cachePost({
		type="message",
		name=plr:Nick(), message=msg,
		teamName=team.GetName(plr:Team()), teamColour=tostring(teamColour.r)..","..tostring(teamColour.g)..","..tostring(teamColour.b),
		steamID = plr:SteamID64()
	})
end

function httpCallbackError(reason)
	if verbose then print("GET failed with reason: "..reason) end

	if toggle then
		HTTP({
			failed = function(reason) timer.Simple(0, function() httpCallbackError(reason) end) end,
			success = httpCallback,
			method = "GET",
			url = "http://" .. connection
		})
	end
end

function httpCallback(statusCode, content, headers)
	if statusCode != 200 then
		if verbose then print("GET failed with status code " .. tostring(statusCode)) end
	elseif content != "none" then
		JSON = util.JSONToTable(content)

		for _, msg in pairs(JSON) do
			print("[Discord | "..msg[4].."] " .. msg[1] .. ": " .. msg[2])
			local colour = Color(msg[3][1], msg[3][2], msg[3][3])

			net.Start("GModRelay.NetworkMsg")
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
			failed = function(reason) timer.Simple(0, function() httpCallbackError(reason) end) end,
			success = httpCallback,
			method = "GET",
			url = "http://" .. connection
		})
	end
end

concommand.Add("startRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() and not toggle then
		toggle = true

		hook.Add("PlayerSay", "GModRelay.CacheChat", onChat)
		hook.Add("PlayerInitialSpawn", "GModRelay.CacheJoins", function(plr) cachePost({type="join", name=plr:Nick()}) end)
		hook.Add("PlayerDisconnected", "GModRelay.CacheLeaves", function(plr)
			cachePost({type="leave", name=plr:Nick()})

			-- Edge case: if this leave event caused the server to go into hibernation, manually post the cache now
			if not sv_hibernate_think:GetBool() and player.GetCount() == 1 then
				HTTP({
					method = "POST",
					url = "http://"..connection,
					body = util.TableToJSON(toPost),
					type = "application/json"
				})
				toPost = {}
			end
		end)
		hook.Add("PlayerDeath", "GModRelay.CacheDeaths", function(vic, inf, atk)
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
			url = "http://"..connection
		})

		hook.Add("Tick", "GModRelay.Post", function()
			tickTimer = (tickTimer + 1) % postInterval
			if tickTimer ~= 0 or #table.GetKeys(toPost) == 0 then return end

			HTTP({
				method = "POST",
				url = "http://"..connection,
				body = util.TableToJSON(toPost),
				type = "application/json"
			})
			toPost = {}
		end)

		print("Relay started")
		HTTP({
			method = "POST",
			url = "http://"..connection,
			body = '{"type":"custom","body":"Relay client connected!"}',
			type = "application/json"
		})
	end
end)
concommand.Add("stopRelay", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() and toggle then
		toggle = false

		hook.Remove("PlayerSay", "GModRelay.CacheChat")
		hook.Remove("PlayerInitialSpawn", "GModRelay.CacheJoins")
		hook.Remove("PlayerDisconnected", "GModRelay.CacheLeaves")
		hook.Remove("PlayerDeath", "GModRelay.CacheDeaths")

		hook.Remove("Tick", "GModRelay.Post")

		print("Relay stopped")
		cachePost({type="custom", body="Relay client disconnected"})

		-- POST any remaining messages including the disconnect one
		HTTP({
			method = "POST",
			url = "http://"..connection,
			body = util.TableToJSON(toPost),
			type = "application/json"
		})
		toPost = {}
	end
end)