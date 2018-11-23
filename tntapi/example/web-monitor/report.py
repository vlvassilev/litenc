#!/usr/bin/python

# Usage:
# $> ./report.py before.xml after.xml
#1. Period:
#+------------+---------------------+---------------------+--------------+
#|    node    |       start         |         stop        |     period   |
#+------------+---------------------+---------------------+--------------+
#| middle     | 2018-09-20T09:21:08 | 2018-09-20T09:22:30 |       82.000 |
#| local      | 2018-09-20T09:21:08 | 2018-09-20T09:22:30 |       82.000 |
#| remote     | 2018-09-20T09:21:08 | 2018-09-20T09:22:30 |       82.000 |
#+------------+---------------------+---------------------+--------------+


import lxml
from lxml import etree
import time
import sys, os
import argparse
from datetime import datetime
import tntapi

period_default=20

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network"}
def main():

	before_config=etree.parse(sys.argv[1])
	before_networks = before_config.xpath('/nc:config/nd:networks',namespaces=namespaces)[0]
	before_network = before_networks.xpath('nd:network',namespaces=namespaces)[0]

	after_config=etree.parse(sys.argv[2])
	after_networks = after_config.xpath('/nc:config/nd:networks',namespaces=namespaces)[0]
	after_network = after_networks.xpath('nd:network',namespaces=namespaces)[0]


	t1 = tntapi.parse_network_nodes(before_network)
	t2 = tntapi.parse_network_nodes(after_network)
	delta = tntapi.get_network_counters_delta(before_network,after_network)

	before=tntapi.strip_namespaces(before_network)
	after=tntapi.strip_namespaces(after_network)

	print("1. Period:")
	print("+------------+---------------------+---------------------+--------------+")
	print("|    node    |       start         |         stop        |     period   |")
	print("+------------+---------------------+---------------------+--------------+")
	node_period={}
	nodes = after.xpath('node')
	periods=tntapi.get_datetime_delta(before, after)
	for node in nodes:
		node_id = node.xpath('node-id')[0].text
		if(periods[node_id]!=None):
			node_period[node_id]=periods[node_id]
			datetime_before=before.xpath("node[node-id='%s']/data/system-state/clock/current-datetime"%(node_id))
			datetime_after=  after.xpath("node[node-id='%s']/data/system-state/clock/current-datetime"%(node_id))
			assert(len(datetime_before)==1 and len(datetime_after)==1)
			dt_before = datetime.strptime(datetime_before[0].text[:19], '%Y-%m-%dT%H:%M:%S')
			dt_after = datetime.strptime(datetime_after[0].text[:19],   '%Y-%m-%dT%H:%M:%S')
			#node_period[node_id] = (dt_after-dt_before).total_seconds()
			#print("node:%s supports /system-state/clock/current-datetime calculated %f sec as period"%(node_id,node_period[node_id]))
			print("| %-10s | %s | %s | %+12s |"%(node_id,datetime_before[0].text[:19],datetime_after[0].text[:19],"%.3f"%node_period[node_id]))
		else:
			node_period[node_id]=period_default
			#print("node:%s does not support /system-state/clock/current-datetime using %f sec as period"%(node_id,node_period[node_id]))

	print("+------------+---------------------+---------------------+--------------+")

# ... TODO ietf-interfaces counters bandwidt ...

	return 0

sys.exit(main())
