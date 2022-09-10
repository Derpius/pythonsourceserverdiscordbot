import os
import atexit
import json

try:
	import discord
except ModuleNotFoundError:
	import revolt
	from src.endpoints.revolt_endpoint import Bot
else:
	from src.endpoints.discord_endpoint import Bot

from src.interface import Context, IUser, Masquerade
from src.config import Config, MessageFormats

# Register clean shutdown function
def onExit(filepath: str):
	print("Performing safe shutdown")

	#for channelID, connectionObj in JSON.items():
	#	JSON[channelID]["server"] = connectionObj["server"].constr
	#json.dump(JSON, open(os.path.join(os.path.dirname(os.path.realpath(filepath)), "data.json"), "w"))

atexit.register(onExit, __file__)

config = json.load(open(os.path.join(os.path.dirname(__file__), "config.json"), "r"))

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

bot = Bot(token, config)

@bot.command
async def greeting(ctx: Context, test: str = "goodbye"):
	'''This is a test command'''
	await ctx.reply(test, Masquerade(ctx.message.author.name, ctx.message.author.avatar))

@bot.event
async def onReady(self) -> None:
	print("Bot loaded!")

bot.run()
