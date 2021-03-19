from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Thread
import atexit
import json
from time import sleep
from urllib.parse import parse_qs
import requests
import re

discordMsgs = {"chat": [], "rcon": []}
sourceMsgs = []
joins = []
leaves = []
deaths = []
custom = []

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
		self.send_response(200)
		self.send_header("Content-type", "application/json")
		self.end_headers()

		global discordMsgs
		if len(discordMsgs["chat"]) == 0 and len(discordMsgs["rcon"]) == 0:
			self.wfile.write(b"none")
			return
		self.wfile.write(bytes(json.dumps(discordMsgs), encoding="utf-8"))	
		discordMsgs = {"chat": [], "rcon": []}
	
	def do_POST(self):
		'''The "receiver" for source server chat'''

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
				match = avatarPattern.search(requests.get(f"http://steamcommunity.com/profiles/{data[k]['steamID']}?xml=1").text).group(1)
				data[k]["icon"] = "http://example.com/" if match is None else match

				global sourceMsgs
				sourceMsgs.append(data[k])
			elif data[k]["type"] == "join":
				global joins
				joins.append(data[k]["name"])
			elif data[k]["type"] == "leave":
				global leaves
				leaves.append(data[k]["name"])
			elif data[k]["type"] == "death":
				global deaths
				deaths.append((data[k]["victim"], data[k]["inflictor"], data[k]["attacker"], data[k]["suicide"] == "1", data[k]["noweapon"] == "1"))
			elif data[k]["type"] == "custom":
				global custom
				custom.append(data[k]["body"])
			else:
				print("Request type param was not valid, got %s" % data[k]["type"])
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
	
	def addMessage(self, msg):
		global discordMsgs
		discordMsgs["chat"].append(msg)
	
	def addRCON(self, command):
		global discordMsgs
		discordMsgs["rcon"].append(command)
	
	def getMessages(self):
		global sourceMsgs
		yield sourceMsgs
		sourceMsgs = []

	def getJoinsAndLeaves(self):
		global joins
		yield joins
		joins = []

		global leaves
		yield leaves
		leaves = []

	def getDeaths(self):
		global deaths
		yield deaths
		deaths = []
		
	def getCustom(self):
		global custom
		yield custom
		custom = []

if __name__ == "__main__":
	r = Relay(8080)
	try:
		while True: sleep(10)
	except KeyboardInterrupt: pass