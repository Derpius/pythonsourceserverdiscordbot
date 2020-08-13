import os
import atexit

import discord
from discord.ext import commands, tasks
from discord.ext.commands import MissingPermissions
from dotenv import load_dotenv
import json

from sourceserver.sourceserver import SourceServer
from sourceserver.exceptions import SourceError
from tablemaker import makeTable

# Initialise variable from local storage
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER = os.getenv("SOURCE_SERVER")
PREFIX = os.getenv("COMMAND_PREFIX")
PING_COOLDOWN = os.getenv("PING_COOLDOWN")

JSON = json.load(open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "data.json"), "r"))

# Define and register clean shutdown function
def onExit(filepath: str):
	print("Performing safe shutdown")
	json.dump(JSON, open(os.path.join(os.path.dirname(os.path.realpath(filepath)), "data.json"), "w"))

atexit.register(onExit, __file__)

# Initialise server and bot instances
srv = SourceServer(SERVER)
bot = commands.Bot(PREFIX)

# Server admin commands (Note, these commands can be run in any channel by people who have manage server perms, even when told not to run)
class ServerCommands(commands.Cog):
	'''Server commands to be used by anyone with manager server permissions'''

	def __init__(self, bot):
		self.pingServer.start() # PyLint sees this as an error, even though it's not
		self.bot = bot

	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def runInChannel(self, ctx, shouldRun: bool = True):
		'''Tells the bot whether to run in this channel or not. If no arg passed, defaults to true'''

		if shouldRun:
			if ctx.channel.id in JSON["channels_to_run_in"]: await ctx.send("The bot is already configured to run in this channel")
			else:
				JSON["channels_to_run_in"].append(ctx.channel.id)
				await ctx.send("Set to run in channel successfully!")
		else:
			if ctx.channel.id not in JSON["channels_to_run_in"]: await ctx.send("The bot is already configured to not run in this channel")
			else:
				JSON["channels_to_run_in"].remove(ctx.channel.id)
				await ctx.send("Set to not run in channel successfully!")
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def close(self, ctx):
		'''Closes the connection to the server'''
		if srv.isClosed: await ctx.send("Server is already closed"); return

		srv.close()
		await ctx.send("Server closed successfully!\nReconnect with `!retry`")
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def retry(self, ctx):
		'''Attempts to reconnect to the server'''
		if not srv.isClosed: await ctx.send("Server is already connected"); return

		srv.retry()
		if srv.isClosed: await ctx.send("Failed to reconnect to server")
		else: await ctx.send("Successfully reconnected to server!")
	
	@commands.command()
	@commands.has_permissions(manage_guild=True)
	async def notifyIfDown(self, ctx, personToNotify: discord.User, shouldNotify: bool = True):
		'''Tells the bot to change notification status for a person. If no toggle passed, defaults to true'''

		if personToNotify.bot: await ctx.send("Bots cannot be notified if the server is down"); return

		if shouldNotify:
			if ctx.message.author.id in JSON["people_to_notify_if_down"]: await ctx.send(f"The bot is already configured to notify {personToNotify.name}")
			else:
				JSON["people_to_notify_if_down"].append(personToNotify.id)
				await ctx.send(f"{personToNotify.name} will now be notified if the server is down")
		else:
			if ctx.message.author.id not in JSON["people_to_notify_if_down"]: await ctx.send(f"The bot is already configured to not notify {personToNotify.name}")
			else:
				JSON["people_to_notify_if_down"].remove(personToNotify.id)
				await ctx.send(f"{personToNotify.name} will no longer be notified if the server is down")

	# Cog error handler
	async def cog_command_error(self, ctx, error):
		if isinstance(error, MissingPermissions):
			await ctx.send(f"You don't have permission to run that command <@{ctx.message.author.id}>")
		else: raise error
	
	# Tasks
	def cog_unload(self):
		self.pingServer.cancel() # PyLint sees this as an error, even though it's not
	
	@tasks.loop(minutes=int(PING_COOLDOWN))
	async def pingServer(self):
		if srv.isClosed: return
		try: srv.ping()
		except SourceError:
			for personToNotify in JSON["people_to_notify_if_down"]:
				user = bot.get_user(personToNotify)
				await user.send(f'''
				**WARNING:** The Source Dedicated Server assigned to this bot is down!\n*You are receiving this message as you are set to be notified if the server goes down at {self.bot.guilds[0].name}*
				''')
			
			srv.close()

# User commands
class UserCommands(commands.Cog):
	@commands.command()
	async def players(self, ctx):
		'''Gets all players on the server'''

		_, plrs = srv.getPlayers()
		simplifiedPlayers = [(player[1], player[2], round(player[3] / 60**2, 1)) for player in plrs]
		table = makeTable(("Name", "Score", "Time on Server (hours)"), simplifiedPlayers)
		await ctx.send("Players on the server:\n```\n" + table + "\n```")
	
	# Command validity checks
	async def cog_check(self, ctx):
		if srv.isClosed and ctx.channel.id in JSON["channels_to_run_in"]:
			await ctx.send("Server is closed, please try again later")
			return False
		
		return ctx.channel.id in JSON["channels_to_run_in"]

	# Cog error handler
	async def cog_command_error(self, ctx, error):
		if isinstance(error, SourceError):
			await ctx.send(f"A server error occured, see the logs for details")
			print(error.message)
			return
		if isinstance(error, commands.errors.CheckFailure): return
		
		raise error

bot.add_cog(ServerCommands(bot))
bot.add_cog(UserCommands(bot))
bot.run(TOKEN)