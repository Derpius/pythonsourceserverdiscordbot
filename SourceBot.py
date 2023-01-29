import asyncio
from datetime import timedelta
import os
import signal
import json
import random
import subprocess
from file_read_backwards import FileReadBackwards
import re
import sys

from sourceserver.exceptions import SourceError

from src.interface import Context, Embed, IEmoji, IGuild, IMessage, IRole, IUser, Masquerade, Permission
from src.config import Backend, Config, MessageFormats
from src.data import Server, Servers
from src.utils import formatTimedelta, Colour
from src.relay import Relay
from src.infopayload import InfoPayload
from src.cli import getCLIArgs

IP_PATTERN = re.compile("(?:(?:[0-9]|[0-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[0-9][0-9]|[0-9])")

args = getCLIArgs()

config = None
with open(args.config, "r") as f:
	config = json.load(f)

token = config["token"]
config = Config.fromJSON(config)

if config.backend == Backend.Discord:
	from src.endpoints.discord import Bot
elif config.backend == Backend.Revolt:
	from src.endpoints.revolt_endpoint import Bot
else:
	raise Exception("Invalid backend in config")

data = None
mode = "r" if os.path.exists(args.data) else "w+"
with open(args.data, mode) as f:
	try:
		data = json.load(f)
	except json.decoder.JSONDecodeError:
		data = dict()

data = Servers(data)

# Register clean shutdown function
def onExit(_signo, _stack_frame):
	print("Performing safe shutdown")

	with open(args.data, "w+") as f:
		json.dump(data.encode(), f)

	sys.exit(0)

signal.signal(signal.SIGINT, onExit)
signal.signal(signal.SIGTERM, onExit)

bot = Bot(token, config)
relay = Relay(config.relayPort)
autoclosed = []
infoPayloads: dict[int, InfoPayload] = {}

async def checkChannelBound(ctx: Context) -> bool:
	if data.channelBound(ctx.channel): return True

	await ctx.reply("This channel isn't connected to a server")
	return False

async def checkChannelOnline(ctx: Context) -> bool:
	if data[ctx.channel].isClosed:
		await ctx.reply("Server is closed, please try again later")
		return False
	return True

async def checkPerms(ctx: Context) -> bool:
	if not ctx.author.hasPermission(Permission.ManageGuild):
		await ctx.reply(f"You don't have permission to run that command {ctx.author}")
		return False
	return True

def getGuildInfo(guild: IGuild) -> InfoPayload:
	'''Get the appropriate InfoPayload for this context, or create one if none exists'''
	if guild.id not in infoPayloads:
		# Create an info payload for this guild if none exists
		payload = InfoPayload(config.backend)
		
		payload.setRoles(guild.roles)
		payload.setEmojis(guild.emojis)
		payload.setMembers(guild.members)

		infoPayloads[guild.id] = payload
	return infoPayloads[guild.id]

def setupConStr(guild: IGuild, constr: str):
	'''Perform initialisation for a new relaying constring'''
	relay.addConStr(constr)
	payload = getGuildInfo(guild)
	payload.addConStr(constr)
	relay.setInitPayload(constr, payload.encode())

def removeConStr(guild: IGuild, constr: str):
	'''Perform deinitialisation of a relaying constring'''
	relay.removeConStr(constr)
	if guild.id in infoPayloads:
		infoPayloads[guild.id].removeConStr(constr)

@bot.command
async def connect(ctx: Context, connectionString: str):
	'''Adds a connection to a source server to this channel'''
	if not await checkPerms(ctx): return

	# Validate the request
	if data.channelBound(ctx.channel):
		existingConnection = data[ctx.channel].constr
		if connectionString == existingConnection:
			await ctx.reply(f"This channel is already connected to `{existingConnection}`")
			return
		await ctx.reply(f"This channel is connected to `{existingConnection}`, use `{config.prefix}disconnect` first to connect to a different server")
		return

	# Attempt to connect to the server provided
	try: server = Server(connectionString, False)
	except SourceError as e: await ctx.reply("Error, " + e.message.split(" | ")[1])
	except ValueError: await ctx.reply("Connection string invalid")
	else:
		if server.isClosed: await ctx.reply("Failed to connect to server")
		else:
			data.bindChannel(ctx.channel, server)
			await ctx.reply("Successfully connected to server!")

@bot.command
async def disconnect(ctx: Context):
	'''Removes this channel's connection to a source server'''
	if not await checkPerms(ctx): return
	if not await checkChannelBound(ctx): return

	if data[ctx.channel].relay:
		removeConStr(ctx.guild, data[ctx.channel].constr)

	data.unbindChannel(ctx.channel)
	await ctx.reply("Connection removed successfully!")

@bot.command
async def close(ctx: Context):
	'''Closes the connection to the server'''
	if not await checkPerms(ctx): return
	if not await checkChannelBound(ctx): return

	if data[ctx.channel].isClosed:
		await ctx.reply("Server is already closed")
		return

	if data[ctx.channel].relay:
		removeConStr(ctx.guild, data[ctx.channel].constr)

	data[ctx.channel].close()
	await ctx.reply(f"Server closed successfully!\nReconnect with `{config.prefix}retry`")

@bot.command
async def retry(ctx: Context):
	'''Attempts to reconnect to the server'''
	if not await checkPerms(ctx): return
	if not await checkChannelBound(ctx): return

	if not data[ctx.channel].isClosed:
		await ctx.reply("Server is already connected")
		return

	data[ctx.channel].retry()
	if data[ctx.channel].isClosed:
		await ctx.reply("Failed to reconnect to server")
	else:
		if data[ctx.channel]:
			setupConStr(ctx.guild, data[ctx.channel].constr)
		
		data[ctx.channel].timeSinceDown = -1
		await ctx.reply("Successfully reconnected to server!")

		if ctx.channel.id in autoclosed:
			# Create a list of all valid user IDs
			# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
			validIDs = []

			# For every person set to be notified, send them a DM to say the server is back online
			for personToNotify in data[ctx.channel].toNotify:
				member = await ctx.guild.fetchMember(personToNotify)
				if not member: continue

				validIDs.append(personToNotify)

				await member.send(f'''
				The Source Dedicated Server `{data[ctx.channel]._info["name"] if data[ctx.channel]._info != {} else "unknown"}` @ `{data[ctx.channel].constr}` assigned to this bot just came back up!\n*You are receiving this message as you are set to be notified regarding server outage at `{ctx.guild.name}`*
				''')

			data[ctx.channel].toNotify = validIDs
			autoclosed.remove(ctx.channel.id)

@bot.command
async def constring(ctx: Context):
	'''Prints the current constring of the connected server'''
	if await checkChannelBound(ctx):
		await ctx.reply(f"`{data[ctx.channel].constr}`")

@bot.command
async def status(ctx: Context):
	'''Tells you whether the connection to the server is closed, invalid, or open'''
	if not await checkChannelBound(ctx): return
	if not await checkChannelOnline(ctx): return

	ping = None
	try: ping = data[ctx.channel].ping()
	except SourceError as e:
		await ctx.reply(f"Connection to server isn't closed internally, however failed to ping the server with exception `{e.message}`")
		return

	await ctx.reply(f"Server online, ping {ping:.0f}. (Note that the ping is from the location of the bot)")

@bot.command
async def info(ctx: Context, infoName: str = None):
	'''Gets server info, all if no name specified\nSee https://github.com/Derpius/pythonsourceserver/wiki/SourceServer#the-info-property-values'''
	if not await checkChannelBound(ctx): return
	if not await checkChannelOnline(ctx): return

	try: info = data[ctx.channel].info
	except SourceError as e:
		await ctx.reply("Unable to get info")
		print(e.message)
		return

	if infoName is None:
		embed = Embed(
			title="Server Info",
			description="{name} is playing {game} on {map}".format(**info),
			colour=config.accentColour
		)

		embed.addField(name="Players", value="{players}/{max_players}".format(**info))
		embed.addField(name="Bots", value=str(info["bots"]))
		embed.addField(name=u"\u200B", value=u"\u200B")

		embed.addField(name="VAC", value=("yes" if info["VAC"] == 1 else "no"))
		embed.addField(name="Password", value=("yes" if info["visibility"] == 1 else "no"))
		embed.addField(name=u"\u200B", value=u"\u200B")

		if info["game"] == "The Ship":
			embed.addField(name="Mode", value=data[ctx.channel].MODES[info["mode"]])
			embed.addField(name="Witnesses Needed", value=str(info["witnesses"]))
			embed.addField(name="Time Before Arrest", value="%d seconds" % info["duration"])

		if "keywords" in info:
			embed.footer = "Keywords: " + info["keywords"]

		await ctx.reply(embed=embed)
		return

	if infoName in ("mode", "witnesses", "duration") and info["game"] != "The Ship":
		await ctx.reply(f"`{infoName}` is only valid on servers running The Ship")
		return

	if infoName not in info.keys():
		await ctx.reply(f"'{infoName}' is invalid, see <https://github.com/Derpius/pythonsourceserver/wiki/SourceServer#the-info-property-values> for a list of valid properties")
		return

	await ctx.reply(f"`{infoName}` is `{info[infoName]}`")

@bot.command
async def players(ctx: Context):
	'''Gets all players on the server'''
	if not await checkChannelBound(ctx): return
	if not await checkChannelOnline(ctx): return

	# Get server details
	try:
		info = data[ctx.channel].info
		count, plrs = data[ctx.channel].getPlayers()
		isTheShip = info["game"] == "The Ship"
		srvName = info["name"]
	except SourceError as e:
		await ctx.reply("Unable to get players")
		print(e.message)
		return

	if count == 0:
		await ctx.reply("Doesn't look like there's anyone online at the moment, try again later")
		return

	# Title
	title = f"Players on server {srvName}"

	# Truncate title if needed
	if len(title) > 256: title = title[:253] + "..."
	
	# Body
	body = ""
	for player in plrs:
		if player[1] == "": continue

		body += f"*{player[1]}*\n"
		if not isTheShip:
			body += f"Score: {player[2]} | Time on server: {formatTimedelta(timedelta(seconds=player[3]))}\n\n"
		else:
			body += f"Score: {player[2]} | Deaths: {player[4]} | Money: {player[5]}\n\n"
	
	# Truncate body if needed (may be replaced with a page system in future)
	if len(body) > 4096: body = body[:4093] + "..."

	# Send
	await ctx.reply(embed=Embed(title=title, description=body, colour=config.accentColour))

@bot.command
async def rules(ctx: Context, ruleName: str = None):
	'''
	Gets a rule's value from the server or all if none specified (Discord embed char limit permitting)\n
	Note, only people with manage server perms can get all rules to reduce spam
	'''
	if not await checkChannelBound(ctx): return
	if not await checkChannelOnline(ctx): return

	try: rules = data[ctx.channel].rules
	except SourceError as e:
		await ctx.reply("Unable to get rules")
		print(e.message)
		return

	if not ruleName:
		if not ctx.author.hasPermission(Permission.ManageGuild):
			await ctx.reply(f"You don't have permission to show all rules for anti-spam reasons {ctx.author}")
			return

		embed = Embed(
			title="Server Rules",
			description="All rules the server uses\n*Note: embeds are capped at 6000 chars, so you may not see all rules*",
			colour=config.accentColour
		)

		ruleString = ""
		page = 0
		count = 0
		for key, val in rules.items():
			if page == 5: break
			if len(ruleString) + len(key) + len(str(val)) + 2 >= 1024:
				page += 1
				embed.addField(name=u"\u200B\n" + str(page) + "\n" + u"\u00AF" * 10, value=ruleString[2:], inline=False)
				ruleString = ""

			ruleString += ", {0}: {1}".format(key, val)
			count += 1

		embed.footer = "%d out of %d rules could be shown" % (count, len(rules.keys()))
		await ctx.reply(embed=embed)
		return

	if ruleName not in rules:
		await ctx.reply(f"The rule '{ruleName}' doesn't exist")
		return

	await ctx.reply(f"{ruleName}: {rules[ruleName]}")

@bot.command
async def notify(ctx: Context, target: IUser = None):
	'''
	Tells the bot to notify you or a person of your choice regarding server outage (loss of server connection, and reconnection to a dropped server).  
	Passing a person without you having manage server perms is not allowed (unless that person is yourself).
	'''
	if not await checkChannelBound(ctx): return

	affectingSelf = target is None
	if target:
		if not ctx.author.hasPermission(Permission.ManageGuild) and ctx.author.id != target.id:
			await ctx.reply(f"You don't have permission to set the notification status for other people {ctx.author}")
			return
	else: target = ctx.author

	if target.bot: await ctx.reply("Bots cannot be notified regarding server outage"); return

	if target.id in data[ctx.channel].toNotify:
		await ctx.reply("Already configured to notify " + ("you" if affectingSelf else str(target)))
	else:
		data[ctx.channel].toNotify.append(target.id)
		await ctx.reply(f"{'You' if affectingSelf else str(target)} will now be notified regarding server outage")

@bot.command
async def dontNotify(ctx: Context, target: IUser = None):
	'''
	Tells the bot to stop notifying you or a person of your choice regarding server outage (loss of server connection, and reconnection to a dropped server).  
	Passing a person without you having manage server perms is not allowed (unless that person is yourself).
	'''
	if not await checkChannelBound(ctx): return

	affectingSelf = target is None
	if target:
		if not ctx.author.hasPermission(Permission.ManageGuild) and ctx.author.id != target.id:
			await ctx.reply(f"You don't have permission to set the notification status for other people {ctx.author}")
			return
	else: target = ctx.author

	if target.id not in data[ctx.channel].toNotify:
		await ctx.reply("Already configured to not notify " + ("you" if affectingSelf else str(target)))
	else:
		data[ctx.channel].toNotify.remove(target.id)
		await ctx.reply(f"{'You' if affectingSelf else str(target)} will no longer be notified regarding server outage")

@bot.command
async def peopleToNotify(ctx: Context):
	'''
	Lists all people set to be notified
	'''
	if not await checkChannelBound(ctx): return

	if not data[ctx.channel].toNotify: # If no one is set to be notified don't bother building a message
		await ctx.reply(f"No one is set to be notified regarding server outage\n*use `{config.prefix}notify` to set someone to be notified, and `{config.prefix}dontNotify` to disable notifications*")
		return

	# As with the actual ping task, we save a list of valid IDs and replace the existing list with this one after the loop
	validIDs = []

	# Message to be sent
	msg = "*The following people are set to be notified regarding outage from the server linked to this channel:*\n"

	for userID in data[ctx.channel].toNotify:
		member = await ctx.guild.fetchMember(userID)
		if not member: continue

		validIDs.append(userID)
		msg += (str(ctx.author) if ctx.author.id == userID else f"`{member.displayName}`") + ", "

	data[ctx.channel].toNotify = validIDs
	await ctx.reply(msg[:-2])

@bot.command
async def enableRelay(ctx: Context):
	'''Enables the relay in this channel'''
	if not await checkPerms(ctx): return
	if not await checkChannelBound(ctx): return
	if not await checkChannelOnline(ctx): return

	if data[ctx.channel].relay:
		await ctx.reply("The relay is already enabled")
		return

	if relay.isConStrAdded(data[ctx.channel].constr):
		await ctx.reply("The relay is already handling this server in another channel, please disable it there first")
		return

	data[ctx.channel].relay = True

	# Init on relay server
	setupConStr(ctx.guild, data[ctx.channel].constr)

	await ctx.reply(f"Relay enabled, use `{config.prefix}disableRelay` to disable")

@bot.command
async def disableRelay(ctx: Context):
	'''Disables the relay in this channel'''
	if not await checkPerms(ctx): return
	if not await checkChannelBound(ctx): return

	if not data[ctx.channel].relay:
		await ctx.reply("The relay is already disabled")
		return

	data[ctx.channel].relay = False

	if not data[ctx.channel].isClosed:
		removeConStr(ctx.guild, data[ctx.channel].constr)

	await ctx.reply(f"Relay disabled, use `{config.prefix}enableRelay` to re-enable")

@bot.command
async def rcon(ctx: Context):
	'''
	Runs a string in the relay client's console  
	(may not be supported by all clients)
	'''
	if not await checkPerms(ctx): return
	if not await checkChannelBound(ctx): return
	if not await checkChannelOnline(ctx): return

	if not data[ctx.channel].relay:
		await ctx.reply("The relay isn't enabled for this server")
		return


	sanetised = ctx.message.content[len(config.prefix + "rcon "):].replace("\n", ";") if ctx.message.content else ""
	if len(sanetised) == 0:
		await ctx.reply("No command string specified")
		return

	relay.addRCON(sanetised, data[ctx.channel].constr)
	await ctx.reply(f"Command `{sanetised if len(sanetised) < 256 else sanetised[:256] + '...'}` queued")

@bot.command
async def restart(ctx: Context, configure: str = None):
	'''
	Runs a configurable shell command to restart the server
	'''
	if not await checkPerms(ctx): return
	if not await checkChannelBound(ctx): return

	if configure == "configure":
		if ctx.author.id != ctx.guild.owner.id:
			await ctx.reply("Due to the security risks of executing arbitrary shell commands, only the owner of this server may configure it")
			return

		command = ctx.message.cleanContent[len(config.prefix) + len("restart configure"):]
		command = command.strip()

		if not command:
			await ctx.reply("No command specified")
			return

		data[ctx.channel].restartCmd = command
		await ctx.reply("Restart command set")
		return

	restartCmd = data[ctx.channel].restartCmd
	if not restartCmd:
		await ctx.reply(f"A restart command is not configured for this channel, use `{config.prefix}restart configure [command]` to set one up")
		return

	msg = await ctx.reply("Running restart command...")
	result = subprocess.run(restartCmd, shell=True, capture_output=True, encoding="utf-8")

	output = "No output"
	if result.stdout:
		output = result.stdout
	elif result.stderr:
		output = result.stderr

	await msg.edit("```ansi\n" + output + "\n```")

@bot.command
async def log(ctx: Context, mode: str = None):
	'''
	Outputs latest entries in a logfile with regex search and IP filtering
	'''
	if not await checkChannelBound(ctx): return

	if mode == "configure":
		if ctx.author.id != ctx.guild.owner.id:
			await ctx.reply("Due to the security risks of reading arbitrary files from the system, only the owner of this server may configure it")
			return

		logPath = ctx.message.cleanContent[len(config.prefix) + len("log configure"):]
		logPath = logPath.strip()

		if not logPath:
			await ctx.reply("No log path specified")
			return

		data[ctx.channel].logPath = logPath
		await ctx.reply("Log path set")
		return

	logPath = data[ctx.channel].logPath
	if not logPath:
		await ctx.reply(f"A log path is not configured for this channel, use `{config.prefix}log configure [path]` to set one up")
		return

	search = ctx.message.cleanContent[len(config.prefix) + len("log"):].strip()

	try:
		matchedLines = []
		totalStrLen = 0
		with FileReadBackwards(logPath) as f:
			for line in f:
				line = re.sub(IP_PATTERN, "\033[0;31m███.███.███.███\033[0m", line)
				if search:
					(line, matches) = re.subn(search, lambda match: "\033[1;32m" + match.group() + "\033[0m", line)
					if matches < 1: continue

				matchedLines.append(line)
				totalStrLen += len(line) + 1 # add 1 for newline char
				if totalStrLen > 1000: break
	except:
		await ctx.reply("Failed to read log file")
	else:
		numMatchedLines = len(matchedLines)
		if numMatchedLines == 0:
			await ctx.reply("Nothing found (either the logfile is empty or your search pattern returned no results)")
			return

		matchedLines.reverse()
		await ctx.reply("Found `{numMatchedLines}` lines\n```ansi\n{output}\n```".format(
			numMatchedLines = len(matchedLines),
			output = "\n".join(matchedLines)
		))

@bot.loop(60)
async def pingServer():
	await bot.waitUntilReady()

	for channelID, server in data:
		if server.isClosed:
			if not channelID in autoclosed: continue # If the server was closed manually just continue

			# Attempt to retry the connection to the server
			server.retry()
			if not server.isClosed:
				guild = bot.getChannel(channelID).guild

				if server.relay:
					setupConStr(guild, server.constr)

				server.timeSinceDown = -1

				# Create a list of all valid user IDs
				# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
				validIDs = []

				# For every person set to be notified, send them a DM to say the server is back online
				for personToNotify in server.toNotify:
					member = await guild.fetchMember(personToNotify)
					if not member: continue

					validIDs.append(personToNotify)

					guildName = guild.name
					await member.send(f'''
					The Source Dedicated Server `{server._info["name"] if server._info != {} else "unknown"}` @ `{server.constr}` assigned to this bot just came back up!\n*You are receiving this message as you are set to be notified regarding server outage at `{guildName}`*
					''')

				server.toNotify = validIDs
				autoclosed.remove(channelID)
			continue

		try:
			server.ping()
		except SourceError:
			server.timeSinceDown += 1
			if server.timeSinceDown < config.timeDownBeforeNotify: continue

			guild = bot.getChannel(channelID).guild

			# Create a list of all valid user IDs
			# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
			validIDs = []

			for personToNotify in server.toNotify:
				member = await guild.fetchMember(personToNotify)
				if not member: continue

				validIDs.append(personToNotify)

				guildName = guild.name
				await member.send(f'''
				**WARNING:** The Source Dedicated Server `{server._info["name"] if server._info != {} else "unknown"}` @ `{server.constr}` assigned to this bot is down!\n*You are receiving this message as you are set to be notified regarding server outage at `{guildName}`*
				''')

			server.toNotify = validIDs

			server.close()
			if server.relay:
				removeConStr(guild, server.constr)

			autoclosed.add(channelID)
		else:
			if server.timeSinceDown != -1: server.timeSinceDown = -1

@bot.loop(0.1)
async def getFromRelay():
	await bot.waitUntilReady()
	for channelID, server in data:
		if server.isClosed or not server.relay: continue

		channel = bot.getChannel(channelID)
		if channel.guild.id not in infoPayloads or server.constr not in infoPayloads[channel.guild.id].constrs: continue

		constring = server.constr
		msgs = relay.getMessages(constring)
		for msg in msgs:
			await channel.send(
				msg["message"],
				Masquerade(
					f"[{msg['teamName']}] {msg['name']}",
					msg["icon"],
					Colour(*[int(val) for val in msg["teamColour"].split(",")])
				)
			)

		# Handle custom events
		custom = relay.getCustom(constring)
		for body in custom:
			if len(body) == 0 or body.isspace(): continue
			await channel.send(body)

		# Handle death events
		deaths = relay.getDeaths(constring)
		for death in deaths:
			if death[3] and not death[4]: # suicide with a weapon
				await channel.send(random.choice(config.messageFormats.suicide).format(victim=death[0], inflictor=death[1]))
			elif death[3]: # suicide without a weapon
				await channel.send(random.choice(config.messageFormats.suicideNoWeapon).format(victim=death[0]))
			elif not death[4]: # kill with a weapon
				await channel.send(random.choice(config.messageFormats.kill).format(victim=death[0], inflictor=death[1], attacker=death[2]))
			else: # kill without a weapon
				await channel.send(random.choice(config.messageFormats.killNoWeapon).format(victim=death[0], attacker=death[2]))

		# Handle join and leave events
		# (joins first incase someone joins then leaves in the same tenth of a second, so the leave message always comes after the join)
		joinsAndLeaves = relay.getJoinsAndLeaves(constring)

		for name in joinsAndLeaves[0]:
			await channel.send(random.choice(config.messageFormats.join).format(player=name))
		for name in joinsAndLeaves[1]:
			await channel.send(random.choice(config.messageFormats.leave).format(player=name))

@bot.event
async def onMessage(msg: IMessage):
	if (
		not data.channelBound(msg.channel) or
		not data[msg.channel].relay or
		data[msg.channel].isClosed
	): return

	constring = data[msg.channel].constr
	if len(msg.content) != 0:
		relay.addMessage((
			msg.author.displayName,
			msg.content,
			int(msg.author.colour),
			msg.author.topRole.name,
			msg.cleanContent
		), constring)

	for attachment in msg.attachments:
		relay.addMessage((
			msg.author.displayName,
			attachment,
			int(msg.author.colour),
			msg.author.topRole.name,
			attachment
		), constring)

# InfoPayload Updaters
def updatePayloadConStrs(payload: InfoPayload):
	'''Goes through every constring using this payload and sends them the new data'''
	for constr in payload.constrs:
		relay.setInitPayload(constr, payload.encode())

@bot.event
async def onMemberJoin(member: IUser):
	infoPayloads[member.guild.id].updateMember(member)
	updatePayloadConStrs(infoPayloads[member.guild.id])

@bot.event
async def onMemberLeave(member: IUser):
	infoPayloads[member.guild.id].removeMember(member)
	updatePayloadConStrs(infoPayloads[member.guild.id])

@bot.event
async def onMemberUpdate(member: IUser):
	infoPayloads[member.guild.id].updateMember(member)
	updatePayloadConStrs(infoPayloads[member.guild.id])

@bot.event
async def onGuildRoleCreate(role: IRole):
	infoPayloads[role.guild.id].updateRole(role)
	updatePayloadConStrs(infoPayloads[role.guild.id])

@bot.event
async def onGuildRoleDelete(role: IRole):
	infoPayloads[role.guild.id].removeRole(role)
	updatePayloadConStrs(infoPayloads[role.guild.id])

@bot.event
async def onGuildRoleUpdate(role: IRole):
	infoPayloads[role.guild.id].updateRole(role)
	updatePayloadConStrs(infoPayloads[role.guild.id])

@bot.event
async def onGuildEmojiCreate(emoji: IEmoji):
	infoPayloads[emoji.guild.id].updateEmoji(emoji)
	updatePayloadConStrs(infoPayloads[emoji.guild.id])

@bot.event
async def onGuildEmojiDelete(emoji: IEmoji):
	infoPayloads[emoji.guild.id].removeEmoji(emoji)
	updatePayloadConStrs(infoPayloads[emoji.guild.id])

@bot.event
async def onReady() -> None:
	for channelID, server in data:
		if not server.relay: continue

		channel = bot.getChannel(channelID)
		if not channel: continue

		setupConStr(channel.guild, server.constr)

async def main():
	await bot.start()

try:
	asyncio.run(main())
except KeyboardInterrupt:
	pass
