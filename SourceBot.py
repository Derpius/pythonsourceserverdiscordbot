import src.bot
import atexit
import json

# Register clean shutdown function
def onExit(filepath: str):
	print("Performing safe shutdown")

	#for channelID, connectionObj in JSON.items():
	#	JSON[channelID]["server"] = connectionObj["server"].constr
	#json.dump(JSON, open(os.path.join(os.path.dirname(os.path.realpath(filepath)), "data.json"), "w"))

atexit.register(onExit, __file__)
