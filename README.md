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
Once this is done you'll need to grant access to each server you want to use it on.

Once all of this is done simply run the `bot.py` script, and say `!help` in the Discord server you added it to.  

## Using the chat relay  
The bot also runs a basic HTTP request handler in parallel to act as a relay between a source server and the bot.  
At the moment I've only made a mod for GMod to support this, however most of the heavy lifting is done by the bot, so it doesn't take much to implement a connection to the relay in another game.  

When running `bot.py`, the HTTP server is started immediately, however it won't actually relay any messages to and from a channel until you set which channel to use with the command *(see `!help`)*  

To connect to the relay using the GMod addon, make sure `-allowlocalhttp` is set to allow HTTP requests within the same LAN as the GMod server, and change `connection` in `init.lua` to something other than `localhost:8080` if you've set the bot to use a different port for the relay (in `.env`), or it's running on a different machine. Start up the server and type `startRelay` in console.  

### Custom message formats  
You can define sets of messages in `messageFormats.json` for changing how things like deaths are formatted in Discord, a message is chosen at random from a set depending on the type. Format specifiers for these are encapsulated in curly brackets (`{}`) and are used in string replacement to insert player names and such.  

Note, if any set is left blank (or deleted entirely), then they will be replaced with defaults as needed.

**WARNING:** Make sure you start the bot **before** starting the relay on the source server with `startRelay`, and make sure you close the relay on the source server with `stopRelay` **before** closing the bot.  

## A note on permissions
The commands available are split into two categories:  
* Server Commands  
* User Commands  

Server commands can only be executed by a person with permissions to manage the server.  
User commands can be executed by anyone, but will only work in channels that the bot has been set to run in (see the `!help`)
