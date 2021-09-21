# Python Source Server Query Library Discord Bot
Discord bot for my Python source server query library  
*See https://github.com/Derpius/pythonsourceserver*

## Installation  
The bot needs a few packages to work:  
`pip install -U discord.py`  
`pip install -U python-dotenv`  
`pip install sourceserver`  

Once you have these prerequisites, download `Bot.zip`, and any Source game relay addons if needed, from the latest release.  
Before you can use the bot, you'll need to edit the `.env` file and change **at least** the Discord bot token.  

To get a Discord bot token, you will need to create a bot *(and an application if you dont already have one)* at the [Discord developer portal](https://discord.com/developers).  
Once this is done you'll need to grant access to each server you want to use it on and turn on members intents (used for the info payload).

Once all of this is done simply run the `bot.py` script, and say `!help` in the Discord server you added it to.  

## Using the chat relay  
The bot also runs a basic HTTP request handler in parallel to act as a relay between source servers and the bot.  

To connect a client to the relay server, simply set the `relay_connection` convar if it's not already correct, and use the `relay_start` command.  
If connecting over LAN with GMod, make sure to either set `-allowlocalhttp`, or use one of the many workarounds to bypass it.  
If connecting over WAN make sure to open the port the relay server is set to run on (not recommended for good response times and any possible security issues with the HTTP handler).  

### Custom message formats  
You can define sets of messages in `messageFormats.json` for changing how things like deaths are formatted in Discord, a message is chosen at random from a set depending on the type. Format specifiers for these are encapsulated in curly brackets (`{}`) and are used in string replacement to insert player names and such.  

Note, if any set is left blank (or deleted entirely), then they will be replaced with defaults as needed.  

## A note on permissions
The commands available are split into two categories:  
* Server Commands  
* User Commands  

Server commands can only be executed by a person with permissions to manage the server.  
User commands can be executed by anyone, but will only work in channels that the bot has been set to run in (see the `!help`)
