#!/usr/bin/python
import lxml
from lxml import etree
import time
import sys, os
import argparse
from collections import namedtuple
import tntapi
import yangrpc
from yangcli import yangcli

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network",
	"if":"urn:ietf:params:xml:ns:yang:ietf-interfaces",
	"netconf-node":"urn:tntapi:netconf-node"}

def yangcli_ok_script(yconn, yangcli_script):
	for line in yangcli_script.splitlines():
		line=line.strip()
		if not line:
			continue
		print("Executing: "+line)
		result = tntapi.yangcli(yconn, line)
		ok=result.xpath('./ok')
		if(len(ok)!=1):
			print lxml.etree.tostring(result)
			assert(0)

def main():
	print("""
#Description: Test tntapi.yangcli works
#Procedure:
#1 - Call tntapi.yangcli(conn,"discard-changes")
""")


	parser = argparse.ArgumentParser()
	parser.add_argument("--config", help="Path to the netconf configuration *.xml file defining the configuration according to ietf-networks, ietf-networks-topology and netconf-node models e.g. ./topology.xml")
	args = parser.parse_args()

	tree=etree.parse(args.config)
	network = tree.xpath('/nc:config/nd:networks/nd:network', namespaces=namespaces)[0]

	conns = tntapi.network_connect(network)
	yconns = tntapi.network_connect_yangrpc(network)

	print("#1. Classic NETCONF RPC:")
	result=conns['local'].rpc("""<discard-changes xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"/>""")
	print(lxml.etree.tostring(result))
	ok=result.xpath('nc:ok', namespaces=namespaces)
	assert(len(ok)==1)

	print("#2. YANGCLI to NETCONF RPC:")
	result=tntapi.yangcli(yconns['local'], "discard-changes")
	print(lxml.etree.tostring(result))
	ok=result.xpath('nc:ok', namespaces=namespaces)
	assert(len(ok)==1)

	return 0

sys.exit(main())
