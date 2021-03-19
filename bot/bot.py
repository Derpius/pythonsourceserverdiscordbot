import os
import atexit
from dotenv import load_dotenv
import json
from datetime import timedelta
from typing import Union
import random
import time

import discord
from discord.ext import commands, tasks
from discord.ext.commands import MissingPermissions

from sourceserver.sourceserver import SourceServer
from sourceserver.exceptions import SourceError

from relay.relay import Relay

# Initialise variables from local storage
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("COMMAND_PREFIX")
TIME_DOWN_BEFORE_NOTIFY = int(os.getenv("TIME_DOWN_BEFORE_NOTIFY"))
COLOUR = int(os.getenv("COLOUR"), 16)
PORT = int(os.getenv("RELAY_PORT"))

# Load data from json
JSON = json.load(open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "data.json"), "r"))
relayChannel = JSON[1]
JSON = JSON[0]

for channelID, connectionObj in JSON.items():
	JSON[channelID]["server"] = SourceServer(connectionObj["server"])
	JSON[channelID]["time_since_down"] = -1

# Load custom message formats from json
messageFormats = json.load(open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "messageFormats.json"), "r"))

if "joinMsgs" not in messageFormats.keys() or len(messageFormats["joinMsgs"]) == 0:
	messageFormats["joinMsgs"] = ["`{player}` just joined the server!"]
if "leaveMsgs" not in messageFormats.keys() or len(messageFormats["leaveMsgs"]) == 0:
	messageFormats["leaveMsgs"] = ["`{player}` just left the server"]

if "suicide" not in messageFormats.keys() or len(messageFormats["suicide"]) == 0:
	messageFormats["suicide"] = ["`{victim}` killed themselves with `{inflictor}`"]
if "suicideNoWeapon" not in messageFormats.keys() or len(messageFormats["suicideNoWeapon"]) == 0:
	messageFormats["suicideNoWeapon"] = ["`{victim}` killed themselves"]
if "kill" not in messageFormats.keys() or len(messageFormats["kill"]) == 0:
	messageFormats["kill"] = ["`{attacker}` killed `{victim}` with `{inflictor}`"]
if "killNoWeapon" not in messageFormats.keys() or len(messageFormats["killNoWeapon"]) == 0:
	messageFormats["killNoWeapon"] = ["`{attacker}` killed `{victim}`"]

# Init relay http server
lastAuthor = ["", 0]
r = Relay(PORT)

# Define and register clean shutdown function
def onExit(filepath: str):
	print("Performing safe shutdown")

	for channelID, connectionObj in JSON.items():
		JSON[channelID]["server"] = "%s:%d" % (connectionObj["server"]._ip, connectionObj["server"]._port)
	json.dump([JSON, relayChannel], open(os.path.join(os.path.dirname(os.path.realpath(filepath)), "data.json"), "w"))

atexit.register(onExit, __file__)

# Utility to convert timedelta to formatted string
def formatTimedelta(delta: timedelta) -> str:
	days, seconds = delta.days, delta.seconds
	hours = seconds // 3600
	minutes = (seconds % 3600) // 60
	seconds = seconds % 60

	datetimeStr = []
	if days != 0: datetimeStr.append(f"{days} day{'s' if days != 1 else ''}")
	if hours != 0: datetimeStr.append(f"{hours} hour{'s' if hours != 1 else ''}")
	if minutes != 0: datetimeStr.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
	if seconds != 0: datetimeStr.append(f"{seconds} second{'s' if seconds != 1 else ''}")
	return " ".join(datetimeStr)

# List for logging if a server was closed automatically or not
autoclosed = set()

# Server admin commands (Note, these commands can be run in any channel by people who have manage server perms, even when told not to run)
class ServerCommands(commands.Cog):
	'''Server commands to be used by anyone with manager server permissions'''

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		# pylint: disable=no-member
		self.pingServer.start() # PyLint sees this as an error, even though it's not
		self.getFromRelay.start()

	async def cog_check(self, ctx):
		'''Make sure the person using these commands has manage guild permissions'''
		return ctx.author.guild_permissions.manage_guild

	@commands.command()
	async def connect(self, ctx, connectionString: str):
		'''Adds a connection to a source server to this channel'''
		channelID = str(ctx.channel.id)
		if channelID in JSON.keys():
			existingConnection = f"{JSON[channelID]['server']._ip}:{JSON[channelID]['server']._port}"
			if connectionString == existingConnection:
				await ctx.message.reply("This channel is already connected to that server")
				return
			await ctx.message.reply(f"This channel is already connected to `{existingConnection}`, use `!disconnect` to connect to a different server")
			return

		server = None
		try: server = SourceServer(connectionString)
		except SourceError as e: await ctx.message.reply("Error, " + e.message.split(" | ")[1])
		except ValueError: await ctx.message.reply("Connection string invalid")
		else:
			if server.isClosed: await ctx.message.reply("Failed to connect to server")
			else:
				JSON.update({channelID: {"server": server, "toNotify": [], "time_since_down": -1}})
				await ctx.message.reply("Successfully connected to server!")

	@commands.command()
	async def disconnect(self, ctx):
		'''Removes this channel's connection to a source server'''
		channelID = str(ctx.channel.id)
		if channelID not in JSON.keys(): await ctx.message.reply("This channel isn't connected to a server"); return

		del JSON[channelID]
		await ctx.message.reply("Connection removed successfully!")

	@commands.command()
	async def close(self, ctx):
		'''Closes the connection to the server'''
		channelID = str(ctx.channel.id)
		if channelID not in JSON.keys(): return
		if JSON[channelID]["server"].isClosed: await ctx.message.reply("Server is already closed"); return

		JSON[channelID]["server"].close()
		await ctx.message.reply("Server closed successfully!\nReconnect with `!retry`")

	@commands.command()
	async def retry(self, ctx):
		'''Attempts to reconnect to the server'''
		channelID = str(ctx.channel.id)
		if channelID not in JSON.keys(): return
		if not JSON[channelID]["server"].isClosed: await ctx.message.reply("Server is already connected"); return
		serverCon = JSON[channelID]

		serverCon["server"].retry()
		if serverCon["server"].isClosed: await ctx.message.reply("Failed to reconnect to server")
		else:
			JSON[channelID]["time_since_down"] = -1
			await ctx.message.reply("Successfully reconnected to server!")

			if channelID in autoclosed:
				# Create a list of all valid user IDs
				# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
				validIDs = []

				# For every person set to be notified, send them a DM to say the server is back online
				for personToNotify in serverCon["toNotify"]:
					member = await ctx.guild.fetch_member(personToNotify)
					if member is None: continue

					validIDs.append(personToNotify)

					await member.send(f'''
					The Source Dedicated Server `{serverCon["server"]._info["name"] if serverCon["server"]._info != {} else "unknown"}` @ `{serverCon["server"]._ip}:{serverCon["server"]._port}` assigned to this bot just came back up!\n*You are receiving this message as you are set to be notified regarding server outage at `{ctx.guild.name}`*
					''')

				JSON[channelID]["toNotify"] = validIDs
				autoclosed.remove(channelID)

	@commands.command()
	async def relayHere(self, ctx):
		'''Sets this channel as game chat relay destination'''
		global relayChannel
		relayChannel = ctx.channel.id

		await ctx.message.reply("Relay set successfully!")

	@commands.command()
	async def disableRelay(self, ctx):
		'''Disables relay (note, the relay thread will still run)'''
		global relayChannel
		relayChannel = None

		await ctx.message.reply("Relay disabled, use `!relayHere` to re-enable")
	
	@commands.command()
	async def rcon(self, ctx):
		'''
		Runs a string in the relay client's console  
		(may not be supported by all clients)
		'''
		if ctx.channel.id != relayChannel:
			await ctx.message.reply("Relay is not enabled in this channel")
			return
		
		sanetised = ctx.message.content[len(self.bot.command_prefix + "rcon "):].replace("\n", ";")

		if len(sanetised) == 0:
			await ctx.message.reply("No command string specified")
			return

		r.addRCON(sanetised)
		await ctx.message.reply(f"Command `{sanetised}` queued")

	# Cog error handler
	async def cog_command_error(self, ctx, error):
		if isinstance(error, SourceError):
			await ctx.message.reply(f"A server error occured, see the logs for details")
			print(error.message)
		elif isinstance(error, MissingPermissions):
			await ctx.message.reply(f"You don't have permission to run that command <@{ctx.message.author.id}>")
		elif isinstance(error, commands.errors.MissingRequiredArgument):
			await ctx.message.reply("Command missing required argument, see `!help`")
		else: raise error

	# Tasks
	def cog_unload(self):
		# pylint: disable=no-member
		self.pingServer.cancel() # PyLint sees this as an error, even though it's not
		self.getFromRelay.cancel()

	@tasks.loop(minutes=1)
	async def pingServer(self):
		await self.bot.wait_until_ready()

		for channelID, serverCon in JSON.items():
			if serverCon["server"].isClosed:
				if not channelID in autoclosed: continue # If the server was closed manually just continue
				
				# Attempt to retry the connection to the server
				serverCon["server"].retry()
				if not serverCon["server"].isClosed:
					JSON[channelID]["time_since_down"] = -1

					# Create a list of all valid user IDs
					# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
					validIDs = []

					# For every person set to be notified, send them a DM to say the server is back online
					for personToNotify in serverCon["toNotify"]:
						member = await self.bot.get_channel(int(channelID)).guild.fetch_member(personToNotify)
						if member is None: continue

						validIDs.append(personToNotify)

						guildName = self.bot.get_channel(int(channelID)).guild.name
						await member.send(f'''
						The Source Dedicated Server `{serverCon["server"]._info["name"] if serverCon["server"]._info != {} else "unknown"}` @ `{serverCon["server"]._ip}:{serverCon["server"]._port}` assigned to this bot just came back up!\n*You are receiving this message as you are set to be notified regarding server outage at `{guildName}`*
						''')

					JSON[channelID]["toNotify"] = validIDs
					autoclosed.remove(channelID)
				continue
			try: serverCon["server"].ping()
			except SourceError:
				JSON[channelID]["time_since_down"] += 1
				if serverCon["time_since_down"] < TIME_DOWN_BEFORE_NOTIFY: continue

				# Create a list of all valid user IDs
				# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
				validIDs = []

				for personToNotify in serverCon["toNotify"]:
					member = await self.bot.get_channel(int(channelID)).guild.fetch_member(personToNotify)
					if member is None: continue

					validIDs.append(personToNotify)

					guildName = self.bot.get_channel(int(channelID)).guild.name
					await member.send(f'''
					**WARNING:** The Source Dedicated Server `{serverCon["server"]._info["name"] if serverCon["server"]._info != {} else "unknown"}` @ `{serverCon["server"]._ip}:{serverCon["server"]._port}` assigned to this bot is down!\n*You are receiving this message as you are set to be notified regarding server outage at `{guildName}`*
					''')

				JSON[channelID]["toNotify"] = validIDs
				serverCon["server"].close()
				autoclosed.add(channelID)
			else:
				if JSON[channelID]["time_since_down"] != -1: JSON[channelID]["time_since_down"] = -1

	@tasks.loop(seconds=0.1)
	async def getFromRelay(self):
		await self.bot.wait_until_ready()
		if relayChannel is None: return

		global lastAuthor

		msgs = tuple(r.getMessages())[0]
		for msg in msgs:
			author = [msg["steamID"], time.time()]

			lastMsg = (await self.bot.get_channel(relayChannel).history(limit=1).flatten())[0]
			if (
				author[0] != lastAuthor[0] or
				lastMsg.author.id != self.bot.user.id or
				len(lastMsg.embeds) == 0 or
				lastMsg.embeds[0].footer.text != author[0] or
				author[1] - lastAuthor[1] > 420
			):
				embed = discord.Embed(description=msg["message"], colour=discord.Colour.from_rgb(*[int(val) for val in msg["teamColour"].split(",")]))
				embed.set_footer(text=author[0])
				embed.set_author(name="[%s] %s" % (msg["teamName"], msg["name"]), icon_url=msg["icon"])
				await self.bot.get_channel(relayChannel).send(embed=embed)
				lastAuthor = author
			else:
				embed = discord.Embed(description=lastMsg.embeds[0].description + "\n" + msg["message"], colour=discord.Colour.from_rgb(*[int(val) for val in msg["teamColour"].split(",")]))
				embed.set_footer(text=author[0])
				embed.set_author(name="[%s] %s" % (msg["teamName"], msg["name"]), icon_url=msg["icon"])
				await lastMsg.edit(embed=embed)

		# Handle custom events
		custom = tuple(r.getCustom())[0]
		for body in custom:
			await self.bot.get_channel(relayChannel).send(body)

		# Handle death events
		deaths = tuple(r.getDeaths())[0]
		for death in deaths:
			if death[3] and not death[4]: # suicide with a weapon
				await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["suicide"]).replace("{victim}", death[0]).replace("{inflictor}", death[1]))
			elif death[3]: # suicide without a weapon
				await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["suicideNoWeapon"]).replace("{victim}", death[0]))
			elif not death[4]: # kill with a weapon
				await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["kill"]).replace("{victim}", death[0]).replace("{inflictor}", death[1]).replace("{attacker}", death[2]))
			else: # kill without a weapon
				await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["killNoWeapon"]).replace("{victim}", death[0]).replace("{attacker}", death[2]))

		# Handle join and leave events
		# (joins first incase someone joins then leaves in the same tenth of a second, so the leave message always comes after the join)
		joinsAndLeaves = tuple(r.getJoinsAndLeaves())

		for name in joinsAndLeaves[0]:
			await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["joinMsgs"]).replace("{player}", name))
		for name in joinsAndLeaves[1]:
			await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["leaveMsgs"]).replace("{player}", name))

	@commands.Cog.listener()
	async def on_message(self, msg: discord.Message):
		if msg.channel.id != relayChannel or msg.author.bot: return

		if ( # If the message is using the command prefix, check if it's a valid command
			len(msg.content) > len(self.bot.command_prefix) and
			msg.content[:len(self.bot.command_prefix)] == self.bot.command_prefix
		):
			cmdText = msg.content[len(self.bot.command_prefix):].split()[0]
			for cmd in self.bot.commands:
				if cmd.name == cmdText: return # Don't relay the message if it's a valid bot command

		if msg.author.colour.value == 0: colour = (255, 255, 255)
		else: colour = msg.author.colour.to_rgb()
		if len(msg.content) != 0: r.addMessage((msg.author.display_name, msg.content, colour, msg.author.top_role.name))

		for attachment in msg.attachments:
			r.addMessage((msg.author.display_name, attachment.url, colour, msg.author.top_role.name))

# User commands
class UserCommands(commands.Cog):
	'''Commands to be run by any user in a channel with a connection'''

	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@commands.command()
	async def status(self, ctx):
		'''Tells you whether the connection to the server is closed, invalid, or open'''
		ping = None
		try: ping = JSON[str(ctx.channel.id)]["server"].ping()
		except SourceError as e:
			await ctx.message.reply("Connection to server isn't closed internally, however failed to ping the server with exception `" + e.message + "`")
			return
		
		await ctx.message.reply("Server online, ping %d. (Note that the ping is from the location of the bot)" % ping)

	@commands.command()
	async def info(self, ctx, infoName: str = None):
		'''Gets server info, all if no name specified\nSee https://github.com/100PXSquared/pythonsourceserver/wiki/SourceServer#the-info-property-values'''
		try: info = JSON[str(ctx.channel.id)]["server"].info
		except SourceError as e:
			await ctx.message.reply("Unable to get info")
			print(e.message)
			return
		
		if infoName is None:
			embed = discord.Embed(title="Server Info", description="{name} is playing {game} on {map}".format(**info), colour=COLOUR)

			embed.add_field(name="Players", value="{players}/{max_players}".format(**info), inline=True)
			embed.add_field(name="Bots", value=str(info["bots"]), inline=True)
			embed.add_field(name=u"\u200B", value=u"\u200B", inline=True)

			embed.add_field(name="VAC", value=("yes" if info["VAC"] == 1 else "no"), inline=True)
			embed.add_field(name="Password", value=("yes" if info["visibility"] == 1 else "no"), inline=True)
			embed.add_field(name=u"\u200B", value=u"\u200B", inline=True)

			if info["game"] == "The Ship":
				embed.add_field(name="Mode", value=JSON[str(ctx.channel.id)]["server"].MODES[info["mode"]], inline=True)
				embed.add_field(name="Witnesses Needed", value=str(info["witnesses"]), inline=True)
				embed.add_field(name="Time Before Arrest", value="%d seconds" % info["duration"], inline=True)

			embed.set_footer(text="Keywords: " + info["keywords"])

			await ctx.message.reply(embed=embed)
			return

		if infoName in ("mode", "witnesses", "duration") and info["game"] != "The Ship":
			await ctx.message.reply(f"`{infoName}` is only valid on servers running The Ship")
			return

		if infoName not in info.keys():
			await ctx.message.reply(f"'{infoName}' is invalid, see https://github.com/100PXSquared/pythonsourceserver/wiki/SourceServer#the-info-property-values for a list of valid properties")
			return

		await ctx.message.reply(f"`{infoName}` is `{info[infoName]}`")

	@commands.command()
	async def players(self, ctx):
		'''Gets all players on the server'''

		try:
			count, plrs = JSON[str(ctx.channel.id)]["server"].getPlayers()
			isTheShip = JSON[str(ctx.channel.id)]["server"].info["game"] == "The Ship"
			srvName = JSON[str(ctx.channel.id)]["server"].info["name"]
		except SourceError as e:
			await ctx.message.reply("Unable to get players")
			print(e.message)
			return

		if count == 0:
			await ctx.message.reply("Doesn't look like there's anyone online at the moment, try again later")
			return

		embed = discord.Embed(colour=COLOUR)
		val = ""
		for player in plrs:
			if player[1] == "": continue

			val += "*%s*\n" % player[1]
			if not isTheShip:
				val += "Score: %d | Time on server: %s\n\n" % (player[2], formatTimedelta(timedelta(seconds=player[3])))
			else:
				val += "Score: %d | Deaths: %d | Money: %d\n\n" % (player[2], player[4], player[5])

		embed.add_field(name=f"Players on server {srvName}", value=val, inline=False)
		await ctx.message.reply(embed=embed)

	@commands.command()
	async def rules(self, ctx, ruleName: str = None):
		'''
		Gets a rule's value from the server or all if none specified (Discord embed char limit permitting)\n
		Note, only people with manage server perms can get all rules to reduce spam
		'''
		try: rules = JSON[str(ctx.channel.id)]["server"].rules
		except SourceError as e:
			await ctx.message.reply("Unable to get rules")
			print(e.message)
			return

		if ruleName is None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild:
				await ctx.message.reply(f"You don't have permission to show all rules for anti-spam reasons <@{ctx.message.author.id}>")
				return

			embed = discord.Embed(
				title="Server Rules",
				description="All rules the server uses\n*Note: embeds are capped at 6000 chars, so you may not see all rules*",
				colour=COLOUR
			)

			ruleString = ""
			page = 0
			count = 0
			for key, val in rules.items():
				if page == 5: break
				if len(ruleString) + len(key) + len(str(val)) + 2 >= 1024:
					page += 1
					embed.add_field(name=u"\u200B\n" + str(page) + "\n" + u"\u00AF" * 10, value=ruleString[2:], inline=False)
					ruleString = ""

				ruleString += ", {0}: {1}".format(key, val)
				count += 1

			embed.set_footer(text="%d out of %d rules could be shown" % (count, len(rules.keys())))
			await ctx.message.reply(embed=embed)
			return

		if ruleName not in rules: await ctx.message.reply("The rule '%s' doesn't exist" % ruleName); return

		await ctx.message.reply("{0}: {1}".format(ruleName, rules[ruleName]))

	@commands.command()
	async def notify(self, ctx, target: Union[discord.User, discord.Member] = None):
		'''
		Tells the bot to notify you or a person of your choice regarding server outage (loss of server connection, and reconnection to a dropped server).  
		Passing a person without you having manage server perms is not allowed (unless that person is yourself).
		'''
		affectingSelf = target is None
		if target is not None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild and ctx.message.author.id != target.id:
				await ctx.message.reply(f"You don't have permission to set the notification status for other people <@{ctx.message.author.id}>")
				return
		else: target = ctx.message.author

		if target.bot: await ctx.message.reply("Bots cannot be notified regarding server outage"); return

		if target.id in JSON[str(ctx.channel.id)]["toNotify"]: await ctx.message.reply("Already configured to notify " + ("you" if affectingSelf else f"<@{target.id}>"))
		else:
			JSON[str(ctx.channel.id)]["toNotify"].append(target.id)
			await ctx.message.reply(("You" if affectingSelf else f"<@{target.id}>") + " will now be notified regarding server outage")

	@commands.command()
	async def dontNotify(self, ctx, target: Union[discord.User, discord.Member] = None):
		'''
		Tells the bot to stop notifying you or a person of your choice regarding server outage (loss of server connection, and reconnection to a dropped server).  
		Passing a person without you having manage server perms is not allowed (unless that person is yourself).
		'''
		affectingSelf = target is None
		if target is not None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild and ctx.message.author.id != target.id:
				await ctx.message.reply(f"You don't have permission to set the notification status for other people <@{ctx.message.author.id}>")
				return
		else: target = ctx.message.author

		if target.id not in JSON[str(ctx.channel.id)]["toNotify"]: await ctx.message.reply("Already configured to not notify " + ("you" if affectingSelf else f"<@{target.id}>"))
		else:
			JSON[str(ctx.channel.id)]["toNotify"].remove(target.id)
			await ctx.message.reply(("You" if affectingSelf else f"<@{target.id}>") + " will no longer be notified regarding server outage")

	@commands.command()
	async def peopleToNotify(self, ctx):
		'''
		Lists all people set to be notified
		'''

		if len(JSON[str(ctx.channel.id)]["toNotify"]) == 0: # If no one is set to be notified don't bother building a message
			await ctx.message.reply("No one is set to be notified regarding server outage\n*use `!notify` to mark yourself to be notified, and `!dontNotify` to disable notifications*")
			return

		# As with the actual ping task, we save a list of valid IDs and replace the existing list with this one after the loop
		validIDs = []

		# Message to be sent
		msg = "*The following people are set to be notified regarding outage from the server linked to this channel:*\n"

		for userID in JSON[str(ctx.channel.id)]["toNotify"]:
			member = await ctx.guild.fetch_member(userID)
			if member is None: continue

			validIDs.append(userID)
			msg += (f"<@{ctx.message.author.id}>" if ctx.message.author.id == userID else "`" + member.name + "`") + ", "

		JSON[str(ctx.channel.id)]["toNotify"] = validIDs
		await ctx.message.reply(msg[:-2])

	# Command validity checks
	async def cog_check(self, ctx):
		if str(ctx.channel.id) not in JSON: return False

		if JSON[str(ctx.channel.id)]["server"].isClosed:
			await ctx.message.reply("Server is closed, please try again later")
			return False

		return True

	# Cog error handler
	async def cog_command_error(self, ctx, error):
		if isinstance(error, SourceError):
			await ctx.message.reply(f"A server error occured, see the logs for details")
			print(error.message)
		elif isinstance(error, commands.errors.CheckFailure): pass
		elif isinstance(error, commands.errors.MissingRequiredArgument):
			await ctx.message.reply("Command missing required argument, see `!help`")
		else: raise error

bot = commands.Bot(PREFIX, case_insensitive=True)
bot.add_cog(ServerCommands(bot))
bot.add_cog(UserCommands(bot))
bot.run(TOKEN)