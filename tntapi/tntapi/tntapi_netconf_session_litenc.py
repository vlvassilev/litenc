from lxml import etree
from litenc.litenc import litenc
import time
import datetime
import sys, os
import argparse
from collections import namedtuple
from tntapi.tntapi_strip_namespaces import strip_namespaces

class tntapi_netconf_session_litenc_class:
	def __init__(self):
		return

	def connect(self, host="localhost",port=830,username="root",password=None,timeout=100):
		conn = litenc()
		if(password==None):
			password_str=""
		else:
			password_str="password="+password
		ret = conn.connect(server=host, port=port, user=username, password=password, timeout=timeout)
		if ret != 0:
			print("[FAILED] Connecting to server=%(server)s:" % {'server':host})
			return None
		print("[OK] Connecting to server=%(server)s:" % {'server':host})

		ret = conn.send("""
<hello>
 <capabilities>
  <capability>urn:ietf:params:netconf:base:1.0</capability>\
 </capabilities>\
</hello>
""")
		if ret != 0:
			print("[FAILED] Sending <hello>")
			return None
		(ret, reply_xml)=conn.receive()
		if ret != 0:
			print("[FAILED] Receiving <hello>")
			return None

		print("[OK] Receiving <hello> =%(reply_xml)s:" % {'reply_xml':reply_xml})
		self.litenc_session=conn
		return 0


	def send(self, xml_str):
		self.reply=self.litenc_session.send("""<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">"""+xml_str+"""</rpc>""")

	def receive(self):
		(ret, reply_xml_str)=self.litenc_session.receive()
		assert(ret==0)
		print(reply_xml_str)
		myetree = etree.fromstring(reply_xml_str.encode('ascii'))
		#myetree = strip_namespaces(myetree)
		return myetree

	def rpc(self, rpc_xml_str):
		self.send(rpc_xml_str)
		return self.receive()

	def close(self):
		self.litenc_session.close()

def netconf_session_litenc(host="localhost",port=830,username="root",password="blah",timeout=100):
	x=tntapi_netconf_session_litenc_class()
	res=x.connect(host,port,username,password,timeout)
	if(res==0):
		return x
	else:
		return None
