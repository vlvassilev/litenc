#!/usr/bin/python
from lxml import etree
import litenc
import time
import datetime
import sys, os
import argparse
from collections import namedtuple
from tntapi_strip_namespaces import strip_namespaces

class my_class:
	def __init__(self,host="localhost",port=830,username="root",password=None,timeout=100):
		conn = litenc.litenc()
		if(password==None):
			password_str=""
		else:
			password_str="password="+password
		ret = conn.connect(server=host, port=port, user=username, password=password, timeout=timeout)
		if ret != 0:
			print "[FAILED] Connecting to server=%(server)s:" % {'server':host}
			assert(0)
		print "[OK] Connecting to server=%(server)s:" % {'server':host}

		ret = conn.send("""
<hello>
 <capabilities>
  <capability>urn:ietf:params:netconf:base:1.0</capability>\
 </capabilities>\
</hello>
""")
		if ret != 0:
			print("[FAILED] Sending <hello>")
			assert(0)
		(ret, reply_xml)=conn.receive()
		if ret != 0:
			print("[FAILED] Receiving <hello>")
			assert(0)

		print "[OK] Receiving <hello> =%(reply_xml)s:" % {'reply_xml':reply_xml}
		self.litenc_session=conn


	def send(self, xml_str):
		self.reply=self.litenc_session.send("""<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">"""+xml_str+"""</rpc>""")

	def receive(self):
		(ret, reply_xml_str)=self.litenc_session.receive()
		assert(ret==0)
		myetree = etree.fromstring(reply_xml_str)
		#myetree = strip_namespaces(myetree)
		return myetree

	def rpc(self, rpc_xml_str):
		self.send(rpc_xml_str)
		return self.receive()

def netconf_session_litenc(host="localhost",port=830,username="root",password="blah",timeout=100):
	x=my_class(host,port,username,password,timeout)
	return x
