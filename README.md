# SourceBot
Discord and Revolt compatible bot to provide rich presence and chat relaying for any number of game servers that implement the Source dedicated server UDP query protocol, or completely unrelated servers that a compatible relay client is written for.  

## Dependencies:  
* `pip install -U discord.py` and/or `pip install -U revolt.py`  
* `pip install -U python-dotenv`  
* `pip install -U sourceserver`  

## Installation  
Clone this repository or download the latest release of the bot, along with any game relay clients you want (clone the respective branch or download prepackaged from releases).  

## Configuration
All configuration is done using a combination of a json config file and an environment variable for your bot token (`BOT_TOKEN`), which I recommend saving in a `.env` file.

An example config file has been provided and should be copied from `config.example.json` to `config.json` to avoid merge conflicts when pulling updates.

### Custom message formats  
You can define sets of messages in `messageFormats.json` for changing how things like deaths are formatted in Discord, a message is chosen at random from a set depending on the type. Format specifiers for these are encapsulated in curly brackets (`{}`) and are used in string replacement to insert player names and such.  

Note, if any set is left blank (or deleted entirely), then they will be replaced with defaults as needed.  
