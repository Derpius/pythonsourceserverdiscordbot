import os
import atexit
from dotenv import load_dotenv
import json

import discord
from discord.ext import commands

from sourceserver.sourceserver import SourceServer

from relay import Relay

from cogs.servercommands import ServerCommands
from cogs.usercommands import UserCommands

# Initialise variables from local storage
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("COMMAND_PREFIX")
TIME_DOWN_BEFORE_NOTIFY = int(os.getenv("TIME_DOWN_BEFORE_NOTIFY"))
COLOUR = int(os.getenv("COLOUR"), 16)
PORT = int(os.getenv("RELAY_PORT"))

# Init relay http server
lastAuthor = ["", 0]
r = Relay(PORT)

# Load data from json
JSON = json.load(open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "data.json"), "r"))

for channelID, connectionObj in JSON.items():
	if JSON[channelID]["relay"] == 1: r.addConStr(connectionObj["server"])
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

# Define and register clean shutdown function
def onExit(filepath: str):
	print("Performing safe shutdown")

	for channelID, connectionObj in JSON.items():
		JSON[channelID]["server"] = connectionObj["server"].constr
	json.dump(JSON, open(os.path.join(os.path.dirname(os.path.realpath(filepath)), "data.json"), "w"))

atexit.register(onExit, __file__)

# Set up intents
intents = discord.Intents.default()
intents.members = True

# Initialise bot
bot = commands.Bot(PREFIX, case_insensitive=True, intents=intents)
bot.add_cog(ServerCommands(bot, JSON, r, TIME_DOWN_BEFORE_NOTIFY, messageFormats))
bot.add_cog(UserCommands(bot, JSON, COLOUR))
bot.run(TOKEN)
