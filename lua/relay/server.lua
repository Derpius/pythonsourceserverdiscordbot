local sv_hibernate_think = GetConVar("sv_hibernate_think")
local relay_connection, relay_interval = Relay.RelayConnection, Relay.RelayInterval
local hostport = GetConVar("hostport")

local toggle = false

local toPost = {}
local tickTimer = 0

local gm = gmod.GetGamemode()

function Relay.CachePost(body)
	local nonce = 1
	local key = tostring(math.floor(CurTime()))..string.char(nonce)

	while toPost[key] do
		key = string.SetChar(key, #key, string.char(nonce))
		nonce = nonce + 1
		if nonce > 255 or (nonce > 5 and body.type ~= "message" and body.type ~= "custom") then
			print("Preventing caching messages to avoid relay rate limiting due to spam")
			return
		end
	end

	toPost[key] = body
end
local cachePost = Relay.CachePost

local function onChat(plr, msg, teamCht)
	local teamColour = team.GetColor(plr:Team())
	cachePost({
		type="message",
		name=plr:Nick(), message=msg,
		teamName=team.GetName(plr:Team()), teamColour=tostring(teamColour.r)..","..tostring(teamColour.g)..","..tostring(teamColour.b),
		steamID = plr:SteamID64()
	})
end

local ulxGimpCB, oldOnChat
concommand.Add("relay_start", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() and not toggle then
		toggle = true

		-- ULX gimp and mute support
		if not ulxGimpCB and hook.GetTable().PlayerSay.ULXGimpCheck then
			ulxGimpCB = hook.GetTable().PlayerSay.ULXGimpCheck
			hook.GetTable().PlayerSay.ULXGimpCheck = nil
			oldOnChat = onChat

			onChat = function(plr, msg, teamCht)
				local ulxMsg = ulxGimpCB(plr, msg, teamCht)
				if ulxMsg then
					if ulxMsg ~= "" then oldOnChat(plr, ulxMsg, teamCht) end
					return ulxMsg
				end
				oldOnChat(plr, msg, teamCht)
			end
		end

		hook.Add("PlayerSay", "Relay.CacheChat", onChat)
		hook.Add("PlayerInitialSpawn", "Relay.CacheJoins", function(plr) cachePost({type="join", name=plr:Nick()}) end)
		hook.Add("PlayerDisconnected", "Relay.CacheLeaves", function(plr)
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
		hook.Add("PlayerDeath", "Relay.CacheDeaths", function(vic, inf, atk)
			cachePost({
				type="death",
				victim=vic:Name(), inflictor=inf.Name and inf:Name() or inf:GetClass(), attacker=atk.Name and atk:Name() or atk:GetClass(),
				suicide=vic == atk and "1" or "0", noweapon=inf:GetClass() == atk:GetClass() and "1" or "0"
			})
		end)

		hook.Add("Tick", "Relay.DoHTTP", function()
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
						if statusCode ~= 200 then return end

						JSON = util.JSONToTable(content)

						if JSON["init-info-dirty"] then Relay.UpdateInfo() end

						for _, msg in pairs(JSON.messages.chat) do
							print("[Relay | "..msg[4].."] " .. msg[1] .. ": " .. msg[2])
							local colour = msg[3]
							colour = Color(bit.rshift(colour, 16), bit.band(bit.rshift(colour, 8), 0xff), bit.band(colour, 0xff))

							if hook.Call("Relay.Message", gm, msg[1], msg[2], colour, msg[4], msg[5]) ~= false then
								net.Start("Relay.NetworkMsg")
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
		Relay.UpdateInfo()
	end
end)
concommand.Add("relay_stop", function(plr, cmd, args, argStr)
	if not plr:IsPlayer() and toggle then
		toggle = false

		hook.Remove("PlayerSay", "Relay.CacheChat")
		hook.Remove("PlayerInitialSpawn", "Relay.CacheJoins")
		hook.Remove("PlayerDisconnected", "Relay.CacheLeaves")
		hook.Remove("PlayerDeath", "Relay.CacheDeaths")

		hook.Remove("Tick", "Relay.DoHTTP")

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

concommand.Add("rsay", function(plr, cmd, args, argStr)
	if plr:IsPlayer() then print("Only the server can use this command") end
	if not toggle then print("Please start the relay with startRelay first"); return end

	cachePost({type="custom", body="[CONSOLE]: "..argStr})

	net.Start("Relay.RSay")
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
end, nil, "Same as say except sends to relay too")
