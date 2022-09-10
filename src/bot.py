try:
	import discord
except ModuleNotFoundError:
	import revolt
	from .endpoints.revolt_endpoint import Bot
else:
	from  .endpoints.discord_endpoint import Bot

from .interface import Context, IUser
from .config import Config

bot = Bot("", Config())

@bot.command
async def greeting(ctx: Context, someArg: str = "hello") -> None:
	'''This is a test command'''
	await ctx.reply(someArg)

@bot.event
async def onReady(self) -> None:
	print("Bot loaded!")

bot.run()
