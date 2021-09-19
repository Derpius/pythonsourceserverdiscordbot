local sv_hibernate_think = GetConVar("sv_hibernate_think")
local relay_connection, relay_interval = GetConVar("relay_connection"), GetConVar("relay_interval")
local hostport = GetConVar("hostport")

local toggle = false

local toPost = {}
local tickTimer = 0

local gm = gmod.GetGamemode()

function DiscordRelay.CachePost(body)
	local nonce = 1
	local key = tostring(math.floor(CurTime()))..string.char(nonce)

	while toPost[key] do
		key = string.SetChar(key, #key, string.char(nonce))
		nonce = nonce + 1
		if nonce > 255 or (nonce > 5 and body.type ~= "message" and body.type ~= "custom") then
			print("Preventing caching messages to avoid Discord rate limiting due to spam")
			return
		end
	end

	toPost[key] = body
end
local cachePost = DiscordRelay.CachePost

local function onChat(plr, msg, teamCht)
	local teamColour = team.GetColor(plr:Team())
	cachePost({
		type="message",
		name=plr:Nick(), message=msg,
		teamName=team.GetName(plr:Team()), teamColour=tostring(teamColour.r)..","..tostring(teamColour.g)..","..tostring(teamColour.b),
		steamID = plr:SteamID64()
	})
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
					type = "application/json",
					headers = {["Source-Port"] = hostport:GetString()}
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

		hook.Add("Tick", "DiscordRelay.DoHTTP", function()
			tickTimer = (tickTimer + 1) % relay_interval:GetInt()
			if tickTimer == 0 and #table.GetKeys(toPost) > 0 then
				-- POST cached messages to relay server
				HTTP({
					method = "POST",
					url = "http://"..relay_connection:GetString(),
					body = util.TableToJSON(toPost),
					type = "application/json",
					headers = {["Source-Port"] = hostport:GetString()}
				})
				toPost = {}
			elseif tickTimer == math.floor(relay_interval:GetInt() / 2) then
				-- GET any available messages from relay server
				HTTP({
					success = function(statusCode, content, headers)
						if statusCode != 200 then return end

						JSON = util.JSONToTable(content)

						for _, msg in pairs(JSON.messages.chat) do
							print("[Discord | "..msg[4].."] " .. msg[1] .. ": " .. msg[2])
							local colourHex = tonumber(msg[3], 16)
							local colour = Color(bit.rshift(colourHex, 16), bit.band(bit.rshift(colourHex, 8), 0xff), bit.band(colourHex, 0xff))
							
							if hook.Call("DiscordRelay.Message", gm, msg[1], msg[2], colour, msg[4], msg[5]) ~= false then
								net.Start("DiscordRelay.NetworkMsg")
									net.WriteString(msg[1])
									net.WriteString(msg[2])
									net.WriteColor(colour)
									net.WriteString(msg[4])
									net.WriteString(msg[5])
								net.Broadcast()
							end
						end

						for _, command in ipairs(JSON.messages.rcon) do
							game.ConsoleCommand(command.."\n")
						end
					end,
					method = "GET",
					url = "http://"..relay_connection:GetString(),
					headers = {["Source-Port"] = hostport:GetString()}
				})
			end
		end)

		print("Relay started")
		HTTP({
			method = "POST",
			url = "http://"..relay_connection:GetString(),
			body = '{"0":{"type":"custom","body":"Relay client connected!"}}',
			type = "application/json",
			headers = {["Source-Port"] = hostport:GetString()}
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

		hook.Remove("Tick", "DiscordRelay.DoHTTP")

		print("Relay stopped")
		cachePost({type="custom", body="Relay client disconnected"})

		-- POST any remaining messages including the disconnect one
		HTTP({
			method = "POST",
			url = "http://"..relay_connection:GetString(),
			body = util.TableToJSON(toPost),
			type = "application/json",
			headers = {["Source-Port"] = hostport:GetString()}
		})
		toPost = {}
	end
end)

concommand.Add("dsay", function(plr, cmd, args, argStr)
	if plr:IsPlayer() then print("Only the server can use this command") end
	if not toggle then print("Please start the relay with startRelay first"); return end

	cachePost({type="custom", body="[CONSOLE]: "..argStr})

	net.Start("DiscordRelay.DSay")
	net.WriteString(argStr)
	net.Broadcast()
	print("Console: "..argStr)

	-- If the server is hibernating then manually POST
	if not sv_hibernate_think:GetBool() and player.GetCount() == 0 then
		HTTP({
			method = "POST",
			url = "http://"..relay_connection:GetString(),
			body = util.TableToJSON(toPost),
			type = "application/json",
			headers = {["Source-Port"] = hostport:GetString()}
		})
		toPost = {}
	end
end, nil, "Same as say except sends to Discord too")