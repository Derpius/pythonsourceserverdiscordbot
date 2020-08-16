from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Thread
import atexit
import json
from time import sleep

discordMsgs = []
sourceMsgs = []

def relayThread(port):
	def onExit(filepath: str):
		print("Relay thread shutdown")
		try: server.socket.close()
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

		# Wait for discord messages for 4 minutes. If 4 minutes elapsed, send "none" so the other end can resend the request to avoid timeout
		timeSlept = 0
		while len(discordMsgs) == 0:
			sleep(0.1)
			timeSlept += 0.1

			if timeSlept == 240:
				self.wfile.write(b"none")
				return
		
		self.wfile.write(bytes(json.dumps(discordMsgs), encoding="utf-8"))
		discordMsgs = []
		return
	
	def do_POST(self):
		'''The "receiver" for source server chat'''

		if self.headers["Content-type"] != "application/json":
			self.send_error(400, "Bad Request", "Request MIME type was not application/json")
			self.end_headers()
			return
		
		data = self.rfile.read(int(self.headers['Content-Length'])).decode("utf-8")
		
		try: JSON = json.loads(data)
		except json.JSONDecodeError:
			self.send_error(400, "Invalid JSON", "Body contained invalid JSON syntax")
			self.end_headers()
			return
		
		if not isinstance(JSON, list):
			self.send_error(400, "Invalid JSON", "JSON was not a list")
			self.end_headers()
			return
		
		for msg in JSON:
			if not isinstance(msg, list) or len(msg) != 3:
				self.send_error(400, "Invalid Message", "JSON contained message that was not of the correct format")
				self.end_headers()
				return
			
			global sourceMsgs
			sourceMsgs.append(msg)
		
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
		discordMsgs.append(msg)
	
	def getMessages(self):
		global sourceMsgs
		yield sourceMsgs
		sourceMsgs = []

if __name__ == "__main__":
	r = Relay(8080)

	for i in range(30):
		sleep(1)
		print(i)
	
	r.addMessage(["username", "message"])

	for i in range(30):
		sleep(1)
		print(i)
	
	print(r.getMessages())