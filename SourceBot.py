from calendar import c
import os
import atexit
import json


from sourceserver.exceptions import SourceError

try:
	import discord
except ModuleNotFoundError:
	import revolt
	from src.endpoints.revolt_endpoint import Bot
else:
	from src.endpoints.discord_endpoint import Bot

from src.interface import Context, IUser, Masquerade, Permission
from src.config import Config, MessageFormats
from src.data import Server, Servers

config = None
with open(os.path.join(os.path.dirname(__file__), "config.json"), "r") as f:
	config = json.load(f)

token = config["token"]
config = Config(
	config["prefix"], config["accent-colour"],
	config["time-down-before-notify"],
	config["relay-port"],
	MessageFormats(
		config["message-formats"]["join"], config["message-formats"]["leave"],
		config["message-formats"]["suicide"], config["message-formats"]["suicide-no-weapon"],
		config["message-formats"]["kill"], config["message-formats"]["kill-no-weapon"]
	)
)

data = None
dataPath = os.path.join(os.path.dirname(__file__), "data.json")
mode = "r" if os.path.exists(dataPath) else "w+"
with open(dataPath, mode) as f:
	try:
		data = json.load(f)
	except json.decoder.JSONDecodeError:
		data = dict()

data = Servers(data)

# Register clean shutdown function
def onExit(filepath: str):
	print("Performing safe shutdown")

	with open(dataPath, "w+") as f:
		json.dump(data.encode(), f)
atexit.register(onExit, __file__)

bot = Bot(token, config)
autoclosed = []

async def checkChannelBound(ctx: Context) -> bool:
	if data.channelBound(ctx.channel): return True

	await ctx.reply("This channel isn't connected to a server")
	return False

async def checkPerms(ctx: Context) -> bool:
	if not ctx.author.hasPermission(Permission.ManageGuild):
		await ctx.reply(f"You don't have permission to run that command {ctx.author}")
		return False
	return True

@bot.command
async def connect(ctx: Context, connectionString: str):
	'''Adds a connection to a source server to this channel'''
	if not await checkPerms(ctx): return False

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
	if not await checkPerms(ctx): return False
	if not await checkChannelBound(ctx): return

	if data[ctx.channel].relay:
		pass#self.removeConStr(ctx.guild, self.json[channelID]['server'].constr)

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
		pass#self.removeConStr(ctx.guild, self.json[channelID]['server'].constr)

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
			pass#self.setupConStr(ctx.guild, self.json[channelID]["server"].constr)
		
		data[ctx.channel].timeSinceDown = -1
		await ctx.reply("Successfully reconnected to server!")

		if ctx.channel.id in autoclosed:
			# Create a list of all valid user IDs
			# This works by appending to this list every valid ID, then setting the toNotify list to this list of valid IDs
			validIDs = []

			# For every person set to be notified, send them a DM to say the server is back online
			for personToNotify in data[ctx.channel].toNotify:
				member = await ctx.guild.fetchMember(personToNotify)
				if member is None: continue

				validIDs.append(personToNotify)

				await member.send(f'''
				The Source Dedicated Server `{data[ctx.channel]._info["name"] if data[ctx.channel]._info != {} else "unknown"}` @ `{data[ctx.channel].constr}` assigned to this bot just came back up!\n*You are receiving this message as you are set to be notified regarding server outage at `{ctx.guild.name}`*
				''')

			data[ctx.channel].toNotify = validIDs
			autoclosed.remove(ctx.channel.id)

@bot.command
async def status(ctx: Context):
	'''Tells you whether the connection to the server is closed, invalid, or open'''
	if not await checkChannelBound(ctx): return

	ping = None
	try: ping = data[ctx.channel].ping()
	except SourceError as e:
		await ctx.reply(f"Connection to server isn't closed internally, however failed to ping the server with exception `{e.message}`")
		return

	await ctx.message.reply(f"Server online, ping {ping:.0f}. (Note that the ping is from the location of the bot)")

@bot.event
async def onReady(self) -> None:
	print("Bot loaded!")

bot.run()
