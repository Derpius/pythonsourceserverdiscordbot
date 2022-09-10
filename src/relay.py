from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Thread
import atexit
import json
from time import sleep
import requests
import re
import socket

infoPayloads = {}
payloadDirty = {}

discordMsgs = {}
sourceMsgs = {}

avatarPattern = re.compile(r"<avatarIcon><!\[CDATA\[(.*?)\]\]></avatarIcon>")

# https://stackoverflow.com/a/28950776
def get_ip():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		# doesn't even have to be reachable
		s.connect(('10.255.255.255', 1))
		IP = s.getsockname()[0]
	except Exception:
		print("Unable to retrieve LAN IP")
		IP = '127.0.0.1'
	finally:
		s.close()
	return IP

def relayThread(port):
	def onExit(filepath: str):
		print("Relay thread shutdown")
		try: server.shutdown()
		except: print("Error closing server")

	atexit.register(onExit, __file__)

	# Define server
	server = ThreadedHTTPServer(("", port), Handler)
	print ("Started HTTP relay on port ", port)

	# Listen indefinately for requests
	server.serve_forever()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	pass

class Handler(BaseHTTPRequestHandler):
	def do_GET(self):
		'''The "transmitter" for discord chat (and any flags)'''
		if "Source-Port" not in self.headers:
			self.send_response(400)
			self.end_headers()
			return

		constring = f"{self.client_address[0] if self.client_address[0] != '127.0.0.1' else get_ip()}:{self.headers['Source-Port']}"
		if constring not in discordMsgs:
			self.send_response(403)
			self.end_headers()
			return

		self.send_response(200)
		self.send_header("Content-type", "application/json")
		self.end_headers()

		self.wfile.write(bytes(json.dumps({
			"messages": discordMsgs[constring],
			"init-info-dirty": payloadDirty[constring]
		}), encoding="utf-8"))	
		discordMsgs[constring] = {"chat": [], "rcon": []}

	def do_POST(self):
		'''The "receiver" for source server chat'''
		if "Source-Port" not in self.headers:
			self.send_response(400)
			self.end_headers()
			return

		constring = f"{self.client_address[0] if self.client_address[0] != '127.0.0.1' else get_ip()}:{self.headers['Source-Port']}"
		if constring not in sourceMsgs:
			self.send_response(403)
			self.end_headers()
			return

		if self.headers["Content-type"] != "application/json":
			print(f"Request MIME type of {self.headers['Content-type']} is invalid")
			self.send_error(400, explain=f"Request MIME type of {self.headers['Content-type']} is invalid")
			self.end_headers()
			return

		data = json.loads(self.rfile.read(int(self.headers.get("Content-Length"))))
		for k in sorted(data):
			if "type" not in data[k].keys():
				print("Request type param was not present")
				self.send_error(400, explain="Request type param was not present")
				self.end_headers()
				return

			if data[k]["type"] == "message":
				if "icon" not in data[k]:
					match = avatarPattern.search(requests.get(f"http://steamcommunity.com/profiles/{data[k]['steamID']}?xml=1").text)
					if match is not None: match = match.group(1)
					data[k]["icon"] = "http://example.com/" if match is None else match

				sourceMsgs[constring]["chat"].append(data[k])
			elif data[k]["type"] == "join":
				sourceMsgs[constring]["joins"].append(data[k]["name"])
			elif data[k]["type"] == "leave":
				sourceMsgs[constring]["leaves"].append(data[k]["name"])
			elif data[k]["type"] == "death":
				sourceMsgs[constring]["deaths"].append((data[k]["victim"], data[k]["inflictor"], data[k]["attacker"], data[k]["suicide"] == "1", data[k]["noweapon"] == "1"))
			elif data[k]["type"] == "custom":
				sourceMsgs[constring]["custom"].append(data[k]["body"])
			else:
				print(f"Request type param was not valid, got {data[k]['type']}")
				self.send_error(400, explain="Request type param was not valid")
				self.end_headers()
				return

		self.send_response(200)
		self.end_headers()
		return
	
	def do_PATCH(self):
		'''Request to get the info payload'''
		if "Source-Port" not in self.headers:
			self.send_response(400)
			self.end_headers()
			return

		constring = f"{self.client_address[0] if self.client_address[0] != '127.0.0.1' else get_ip()}:{self.headers['Source-Port']}"
		if constring not in sourceMsgs:
			self.send_response(403)
			self.end_headers()
			return

		self.send_response(200)
		self.end_headers()

		self.wfile.write(bytes(infoPayloads[constring], encoding="utf-8"))
		payloadDirty[constring] = False

class Relay(object):
	'''HTTP chat relay for source servers'''

	def __init__(self, port):
		print("Starting relay thread")
		self.t = Thread(target=relayThread, args=(port,))
		self.t.daemon = True
		self.t.start()
	
	def setInitPayload(self, constring: str, payload: str):
		'''Set the payload to be sent when a client performs an init request'''
		infoPayloads[constring] = payload
		payloadDirty[constring] = True

	def addConStr(self, constring: str):
		discordMsgs[constring] = {"chat": [], "rcon": []}
		sourceMsgs[constring] = {"chat": [], "joins": [], "leaves": [], "deaths": [], "custom": []}
		infoPayloads[constring] = ""
		payloadDirty[constring] = False
	def removeConStr(self, constring: str):
		del discordMsgs[constring]
		del sourceMsgs[constring]
		del infoPayloads[constring]
		del payloadDirty[constring]

	def isConStrAdded(self, constring: str) -> bool:
		return constring in infoPayloads

	def addMessage(self, msg: tuple, constring: str):
		discordMsgs[constring]["chat"].append(msg)

	def addRCON(self, command: str, constring: str):
		discordMsgs[constring]["rcon"].append(command)

	def getMessages(self, constring: str) -> list:
		ret = sourceMsgs[constring]["chat"]
		sourceMsgs[constring]["chat"] = []
		return ret

	def getJoinsAndLeaves(self, constring: str) -> tuple:
		ret = (sourceMsgs[constring]["joins"], sourceMsgs[constring]["leaves"])
		sourceMsgs[constring]["joins"] = []
		sourceMsgs[constring]["leaves"] = []
		return ret

	def getDeaths(self, constring: str) -> list:
		ret = sourceMsgs[constring]["deaths"]
		sourceMsgs[constring]["deaths"] = []
		return ret

	def getCustom(self, constring: str) -> list:
		ret = sourceMsgs[constring]["custom"]
		sourceMsgs[constring]["custom"] = []
		return ret

if __name__ == "__main__":
	r = Relay(8080)
	try:
		while True: sleep(10)
	except KeyboardInterrupt: pass