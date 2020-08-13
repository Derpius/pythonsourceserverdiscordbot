# Python Source Server Query Library Discord Bot
Discord bot for my Python source server query library  
*See https://github.com/100PXSquared/pythonsourceserver*

## Installation
The bot needs a few packages to work:  
`pip install -U discord.py`  
`pip install -U python-dotenv`  
`pip install sourceserver`  

To use the bot itself, download the source code zip *(from releases if you want a stable version)* and move the contents of the `/bot` folder to wherever you want.  
Before you can use the bot, you'll need to edit the `.env` file and change **at least** the Discord bot token and the Source server it links to.  

To get a Discord bot token, you will need to create a bot *(and an application if you dont already have one)* at the [Discord developer portal](https://discord.com/developers).  
Once this is done you'll need to grant access to one or more servers (currently will only connect to a single source server so the usefullness of having the bot in multiple servers is limited)

Once all of this is done simply run the `bot.py` script, and say `!help` in the Discord server you added it to.  

## A note on permissions
The commands available are split into two categories:  
* Server Commands  
* User Commands  

Server commands can only be executed by a person with permissions to manage the server.  
User commands can be executed by anyone, but will only work in channels that the bot has been set to run in (see the `!help`)
