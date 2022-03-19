import SimpleHTTPServer
import SocketServer
import logging
import cgi

import sys
import os
#import pdb

if len(sys.argv) > 2:
	PORT = int(sys.argv[2])
	I = sys.argv[1]
elif len(sys.argv) > 1:
	PORT = int(sys.argv[1])
	I = ""
else:
	PORT = 8000
	I = ""

def update():
	os.system("mv cur.xml prev.xml")
	os.system("get-net topology.xml cur.xml")
	os.system("./report.py prev.xml cur.xml | tee  report.txt")
	os.system("./report-cameras.py prev.xml cur.xml | tee  cameras.html")
	os.system("traffic-graphic --background=traffic-graphic-background.svg --before=prev.xml --after=cur.xml --output=traffic-graphic.svg")
	os.system("diff-net prev.xml cur.xml | tee  diff-net.txt")


class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

	def end_headers(self):
		self.send_my_headers()
		SimpleHTTPServer.SimpleHTTPRequestHandler.end_headers(self)

	def send_my_headers(self):
		self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
		self.send_header("Pragma", "no-cache")
		self.send_header("Expires", "0")

	def do_GET(self):
		#pdb.set_trace()
		#update()
		SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

	def do_POST(self):
		#pdb.set_trace()
		form = cgi.FieldStorage(
			fp=self.rfile,
			headers=self.headers,
			environ={'REQUEST_METHOD':'POST',
			'CONTENT_TYPE':self.headers['Content-Type'],
		})

		for item in form.list:
			print(item)

		if(form.getvalue('cmd')=='set-net'):
			fileitem = form['file']
			open('topology.xml', 'wb').write(fileitem.file.read())
			os.system("set-net topology.xml")
		if(form.getvalue('cmd')=='get-net' or form.getvalue('cmd')=='set-net'):
			update()

		SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

def main():
	Handler = ServerHandler

	httpd = SocketServer.TCPServer(("", PORT), Handler)

	print("Starting tntapi web-monitor example ...")
	print("Serving at: http://%(interface)s:%(port)s" % dict(interface=I or "localhost", port=PORT))
	httpd.serve_forever()

sys.exit(main())
#pdb.run(main())
