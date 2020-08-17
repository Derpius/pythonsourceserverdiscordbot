from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Thread
import atexit
import json
from time import sleep
from urllib.parse import parse_qs

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

		# Wait for discord messages for 1 minute. If 1 minute elapsed, send "none" so the other end can resend the request to avoid timeout
		timeSlept = 0
		while len(discordMsgs) == 0:
			sleep(0.1)
			timeSlept += 0.1

			if timeSlept >= 30:
				self.wfile.write(b"none")
				return
		
		self.wfile.write(bytes(json.dumps(discordMsgs), encoding="utf-8"))
		discordMsgs = []
		return
	
	def do_POST(self):
		'''The "receiver" for source server chat'''

		if self.headers["Content-type"] != "application/x-www-form-urlencoded":
			self.send_error(400, "Bad Request", "Request MIME type was not valid")
			self.end_headers()
			return
		
		data = self.rfile.read(int(self.headers['Content-Length'])).decode("utf-8")

		global sourceMsgs
		sourceMsgs.append(parse_qs(data))
		
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

	sleep(500)