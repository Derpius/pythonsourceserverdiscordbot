from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Thread
import atexit
import json
from time import sleep
import requests
import re

discordMsgs = {"chat": [], "rcon": []}
sourceMsgs = {}

avatarPattern = re.compile(r"<avatarIcon><!\[CDATA\[(.*?)\]\]></avatarIcon>")

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
		'''The "transmitter" for discord chat'''
		if "Source-Port" not in self.headers:
			self.send_response(400)
			self.end_headers()
			return
		
		constring = f"{self.client_address[0]}:{self.headers['Source-Port']}"
		if constring not in discordMsgs:
			self.send_response(403)
			self.end_headers()
			return

		self.send_response(200)
		self.send_header("Content-type", "application/json")
		self.end_headers()

		if len(discordMsgs[constring]["chat"]) == 0 and len(discordMsgs[constring]["rcon"]) == 0:
			self.wfile.write(b"none")
			return
		self.wfile.write(bytes(json.dumps(discordMsgs[constring]), encoding="utf-8"))	
		discordMsgs[constring] = {"chat": [], "rcon": []}
	
	def do_POST(self):
		'''The "receiver" for source server chat'''
		if "Source-Port" not in self.headers:
			self.send_response(400)
			self.end_headers()
			return
		
		constring = f"{self.client_address[0]}:{self.headers['Source-Port']}"
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

class Relay(object):
	'''HTTP chat relay for source servers'''

	def __init__(self, port):
		print("Starting relay thread")
		self.t = Thread(target=relayThread, args=(port,))
		self.t.daemon = True
		self.t.start()

	def addConStr(self, constring: str):
		discordMsgs[constring] = {"chat": [], "rcon": []}
		sourceMsgs[constring] = {"chat": [], "joins": [], "leaves": [], "deaths": [], "custom": []}
	def removeConStr(self, constring: str):
		del discordMsgs[constring]
		del sourceMsgs[constring]
	
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