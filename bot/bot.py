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

	datetimeStr = ""
	if days != 0: datetimeStr += "%d days " % days
	if hours != 0: datetimeStr += "%dhrs " % hours
	if minutes != 0: datetimeStr += "%dmin " % minutes
	if seconds != 0: datetimeStr += "%dsec" % seconds

	return datetimeStr

# Server admin commands (Note, these commands can be run in any channel by people who have manage server perms, even when told not to run)
class ServerCommands(commands.Cog):
	'''Server commands to be used by anyone with manager server permissions'''

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		# pylint: disable=no-member
		self.pingServer.start() # PyLint sees this as an error, even though it's not
		self.getFromRelay.start()
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def connect(self, ctx, connectionString: str):
		'''Adds a connection to a source server to this channel'''

		if ctx.channel.id in JSON.keys():
			connection = (JSON[str(ctx.channel.id)]["server"]._ip, JSON[str(ctx.channel.id)]["server"]._port)
			await ctx.send("This channel is already connected to %s:%d, use `!removeConnection` to remove it" % connection)
			return
		
		try: JSON.update({
			str(ctx.channel.id): {"server": SourceServer(connectionString), "toNotify": [], "time_since_down": -1}
		})
		except SourceError as e: await ctx.send("Error, " + e.message.split(" | ")[1])
		except ValueError: await ctx.send("Connection string invalid")
		else:
			if JSON[str(ctx.channel.id)]["server"].isClosed: await ctx.send("Failed to connect to server")
			else: await ctx.send("Successfully connected to server!")
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def disconnect(self, ctx):
		'''Removes this channel's connection to a source server'''

		if str(ctx.channel.id) not in JSON.keys(): await ctx.send("This channel isn't connected to a server"); return

		del JSON[str(ctx.channel.id)]
		await ctx.send("Connection removed successfully!")
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def close(self, ctx):
		'''Closes the connection to the server'''
		if JSON[str(ctx.channel.id)]["server"].isClosed: await ctx.send("Server is already closed"); return

		JSON[str(ctx.channel.id)]["server"].close()
		await ctx.send("Server closed successfully!\nReconnect with `!retry`")
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def retry(self, ctx):
		'''Attempts to reconnect to the server'''
		if not JSON[str(ctx.channel.id)]["server"].isClosed: await ctx.send("Server is already connected"); return

		JSON[str(ctx.channel.id)]["server"].retry()
		if JSON[str(ctx.channel.id)]["server"].isClosed: await ctx.send("Failed to reconnect to server")
		else:
			JSON[str(ctx.channel.id)]["time_since_down"] = -1
			await ctx.send("Successfully reconnected to server!")
			
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def relayHere(self, ctx):
		'''Sets this channel as game chat relay destination'''
		global relayChannel
		relayChannel = ctx.channel.id

		await ctx.send("Relay set successfully!")
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def disableRelay(self, ctx):
		'''Disables relay (note, the relay thread will still run)'''
		global relayChannel
		relayChannel = None

		await ctx.send("Relay disabled, use `!relayHere` to re-enable")

	# Cog error handler
	async def cog_command_error(self, ctx, error):
		if isinstance(error, SourceError):
			await ctx.send(f"A server error occured, see the logs for details")
			print(error.message)
		elif isinstance(error, MissingPermissions):
			await ctx.send(f"You don't have permission to run that command <@{ctx.message.author.id}>")
		elif isinstance(error, commands.errors.MissingRequiredArgument):
			await ctx.send("Command missing required argument, see `!help`")
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
			if serverCon["server"].isClosed: return
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
					**WARNING:** The Source Dedicated Server `{serverCon["server"]._info["name"] if serverCon["server"]._info != {} else "unknown"}` @ {serverCon["server"]._ip}:{serverCon["server"]._port} assigned to this bot is down!\n*You are receiving this message as you are set to be notified if the server goes down at {guildName}*
					''')
				
				JSON[channelID]["toNotify"] = validIDs
				serverCon["server"].close()
			else:
				if JSON[channelID]["time_since_down"] != -1: JSON[channelID]["time_since_down"] = -1
	
	@tasks.loop(seconds=0.1)
	async def getFromRelay(self):
		await self.bot.wait_until_ready()
		if relayChannel is None: return

		global lastAuthor

		msgs = tuple(r.getMessages())[0]
		for msg in msgs:
			author = [msg["steamID"][0], time.time()]

			lastMsg = (await self.bot.get_channel(relayChannel).history(limit=1).flatten())[0]
			if (
				author[0] != lastAuthor[0] or
				lastMsg.author.id != self.bot.user.id or
				len(lastMsg.embeds) == 0 or
				lastMsg.embeds[0].footer.text != author[0] or
				author[1] - lastAuthor[1] > 420
			):
				embed = discord.Embed(description=msg["message"][0], colour=discord.Colour.from_rgb(*[int(val) for val in msg["teamColour"][0].split(",")]))
				embed.set_footer(text=author[0])
				embed.set_author(name="[%s] %s" % (msg["teamName"][0], msg["name"][0]), icon_url=msg["icon"][0])
				await self.bot.get_channel(relayChannel).send(embed=embed)
				lastAuthor = author
			else:
				embed = discord.Embed(description=lastMsg.embeds[0].description + "\n" + msg["message"][0], colour=discord.Colour.from_rgb(*[int(val) for val in msg["teamColour"][0].split(",")]))
				embed.set_footer(text=author[0])
				embed.set_author(name="[%s] %s" % (msg["teamName"][0], msg["name"][0]), icon_url=msg["icon"][0])
				await lastMsg.edit(embed=embed)

		# Handle join and leave events
		# (joins first incase someone joins then leaves in the same tenth of a second, so the leave message always comes after the join)
		joinsAndLeaves = tuple(r.getJoinsAndLeaves())

		for name in joinsAndLeaves[0]:
			await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["joinMsgs"]).replace("{player}", name))
		for name in joinsAndLeaves[1]:
			await self.bot.get_channel(relayChannel).send(random.choice(messageFormats["leaveMsgs"]).replace("{player}", name))

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

	@commands.Cog.listener()
	async def on_message(self, msg: discord.Message):
		if msg.channel.id != relayChannel or msg.author.bot: return

		if msg.author.colour.value == 0: colour = (255, 255, 255)
		else: colour = msg.author.colour.to_rgb()
		r.addMessage([msg.author.display_name, msg.content, colour, msg.author.top_role.name])

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
			await ctx.send("Connection to server isn't closed internally, however failed to ping the server with exception `" + e.message + "`")
			return
		
		await ctx.send("Server online, ping %d. (Note that the ping is from the location of the bot)" % ping)

	@commands.command()
	async def info(self, ctx, infoName: str = None):
		'''Gets server info, all if no name specified\nSee https://github.com/100PXSquared/pythonsourceserver/wiki/SourceServer#the-info-property-values'''
		try: info = JSON[str(ctx.channel.id)]["server"].info
		except SourceError as e:
			await ctx.send("Unable to get info")
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

			await ctx.send(embed=embed)
			return
		
		if infoName in ("mode", "witnesses", "duration") and info["game"] != "The Ship":
			await ctx.send("%s is only valid on servers running The Ship" % infoName)
			return
		
		if infoName not in info.keys():
			embed = discord.Embed(
				title="'%s' is invalid" % infoName,
				description="See [the wiki](https://github.com/100PXSquared/pythonsourceserver/wiki/SourceServer#the-info-property-values \"Python Source Server Query Library Wiki\")",
				colour=COLOUR
			)
			await ctx.send(embed=embed); return
		
		await ctx.send("%s is " % infoName + str(info[infoName]))
	
	@commands.command()
	async def players(self, ctx):
		'''Gets all players on the server'''

		try:
			count, plrs = JSON[str(ctx.channel.id)]["server"].getPlayers()
			isTheShip = JSON[str(ctx.channel.id)]["server"].info["game"] == "The Ship"
			srvName = JSON[str(ctx.channel.id)]["server"].info["name"]
		except SourceError as e:
			await ctx.send("Unable to get players")
			print(e.message)
			return

		if count == 0:
			await ctx.send("Doesn't look like there's anyone online at the moment, try again later")
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
		await ctx.send(embed=embed)

	@commands.command()
	async def rules(self, ctx, ruleName: str = None):
		'''
		Gets a rule's value from the server or all if none specified (Discord embed char limit permitting)\n
		Note, only people with manage server perms can get all rules to reduce spam
		'''
		try: rules = JSON[str(ctx.channel.id)]["server"].rules
		except SourceError as e:
			await ctx.send("Unable to get rules")
			print(e.message)
			return
		
		if ruleName is None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild:
				await ctx.send(f"You don't have permission to show all rules for anti-spam reasons <@{ctx.message.author.id}>")
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
			await ctx.send(embed=embed)
			return
		
		if ruleName not in rules: await ctx.send("The rule '%s' doesn't exist" % ruleName); return

		await ctx.send("{0}: {1}".format(ruleName, rules[ruleName]))
	
	@commands.command()
	async def notifyIfDown(self, ctx, personToNotify: Union[discord.User, discord.Member] = None):
		'''
		Tells the bot to notify you or a person of your choice when the server is down.
		Passing a person without you having manage server perms is not allowed (unless that person is yourself).
		'''

		if personToNotify is not None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild and ctx.message.author.id != personToNotify.id:
				await ctx.send(f"You don't have permission to set the notification status for other people <@{ctx.message.author.id}>")
				return
		else: personToNotify = ctx.message.author

		if personToNotify.bot: await ctx.send("Bots cannot be notified if the server is down"); return

		if personToNotify.id in JSON[str(ctx.channel.id)]["toNotify"]: await ctx.send(f"Already configured to notify {personToNotify.name}")
		else:
			JSON[str(ctx.channel.id)]["toNotify"].append(personToNotify.id)
			await ctx.send(f"{personToNotify.name} will now be notified if the server is down")
	
	@commands.command()
	async def dontNotifyIfDown(self, ctx, personToNotNotify: Union[discord.User, discord.Member] = None):
		'''
		Tells the bot to stop notifying you or a person of your choice when the server is down.
		Passing a person without you having manage server perms is not allowed (unless that person is yourself).
		'''

		if personToNotNotify is not None:
			if not ctx.channel.permissions_for(ctx.message.author).manage_guild and ctx.message.author.id != personToNotNotify.id:
				await ctx.send(f"You don't have permission to set the notification status for other people <@{ctx.message.author.id}>")
				return
		else: personToNotNotify = ctx.message.author

		if personToNotNotify.id not in JSON[str(ctx.channel.id)]["toNotify"]: await ctx.send(f"Already configured to not notify {personToNotNotify.name}")
		else:
			JSON[str(ctx.channel.id)]["toNotify"].remove(personToNotNotify.id)
			await ctx.send(f"{personToNotNotify.name} will no longer be notified if the server is down")
	
	@commands.command()
	async def peopleToNotify(self, ctx):
		'''
		Lists all people set to be notified, highlighting the person who runs the command
		'''

		# As with the actual ping task, we save a list of valid IDs and replace the existing list with this one after the loop
		validIDs = []

		# Message to be sent
		msg = "*The following people are set to be notified when the Source server linked to this channel goes down:*\n"

		for userID in JSON[str(ctx.channel.id)]["toNotify"]:
			member = await ctx.guild.fetch_member(userID)
			if member is None: continue

			validIDs.append(userID)
			msg += (f"<@{ctx.message.author.id}>" if ctx.message.author.id == userID else "`" + member.name + "`") + ", "
		
		JSON[str(ctx.channel.id)]["toNotify"] = validIDs
		await ctx.send(msg[:-2])
	
	# Command validity checks
	async def cog_check(self, ctx):
		if str(ctx.channel.id) not in JSON: return False

		if JSON[str(ctx.channel.id)]["server"].isClosed:
			await ctx.send("Server is closed, please try again later")
			return False
		
		return True

	# Cog error handler
	async def cog_command_error(self, ctx, error):
		if isinstance(error, SourceError):
			await ctx.send(f"A server error occured, see the logs for details")
			print(error.message)
		elif isinstance(error, commands.errors.CheckFailure): pass
		elif isinstance(error, commands.errors.MissingRequiredArgument):
			await ctx.send("Command missing required argument, see `!help`")
		else: raise error

bot = commands.Bot(PREFIX)
bot.add_cog(ServerCommands(bot))
bot.add_cog(UserCommands(bot))
bot.run(TOKEN)