#!/usr/bin/python
import lxml
import time
import datetime
import sys, os
import argparse
from collections import namedtuple
#from tntapi_netconf_session_ncclient import netconf_session_ncclient
from tntapi_netconf_session_litenc import netconf_session_litenc
from tntapi_strip_namespaces import strip_namespaces

config_transaction_counter = 0
config_transaction_timestamp_started = None
config_transaction_timestamp_completed = None
state_transaction_counter = 0

yangcli_supported=False
try:
	import yangrpc
	from yangcli import yangcli
	print("yangcli supported.")
	yangcli_supported=True
except ImportError:
	print("yangcli not supported.")


def network_connect(network):

	conns={}
	network_id = network.xpath('network-id')
	print("Connecting to network: " + network_id[0].text)
	nodes = network.xpath('node')
	for node in nodes:
		node_id = node.xpath('node-id')[0].text
		server = node.xpath('netconf-connect-params/server')[0].text
		user =node.xpath('netconf-connect-params/user')[0].text
		if(1==len(node.xpath('netconf-connect-params/password'))):
			password=node.xpath('netconf-connect-params/password')[0].text
		else:
			password=None
		ncport = node.xpath('netconf-connect-params/ncport')[0].text

		print "Connect to " + node_id +" (server=%(server)s user=%(user)s) password=%(password)s ncport=%(ncport)s:" % {'server':server, 'user':user, 'password':password, 'ncport':ncport}
		conns[node_id] = netconf_session_litenc(host=server,port=int(ncport),username=user,password=password,timeout=100)

		if conns[node_id] == None:
			print "FAILED connect"
			return(None)
		else:
			print "OK"
	return conns

def network_connect_yangrpc(network):

	yconns={}
	assert(yangcli_supported==True)
	network_id = network.xpath('network-id')
	print("Connecting to YANG network: " + network_id[0].text)
	nodes = network.xpath('node')
	for node in nodes:
		node_id = node.xpath('node-id')[0].text
		server = node.xpath('netconf-connect-params/server')[0].text
		user =node.xpath('netconf-connect-params/user')[0].text
		if(1==len(node.xpath('netconf-connect-params/password'))):
			password=node.xpath('netconf-connect-params/password')[0].text
		else:
			password=None
		ncport = node.xpath('netconf-connect-params/ncport')[0].text

		print "Connect to YANG device " + node_id +" (server=%(server)s user=%(user)s) password=%(password)s ncport=%(ncport)s:" % {'server':server, 'user':user, 'password':password, 'ncport':ncport}
		yconns[node_id] = yangrpc.connect(server, int(ncport), user, password, os.getenv('HOME')+"/.ssh/id_rsa.pub", os.getenv('HOME')+"/.ssh/id_rsa", "--dump-session=nc-session-")

		if yconns[node_id] == None:
			print "FAILED connect"
			return(None)
		else:
			print "OK"
	return yconns

def network_get_state(network, conns, filter=""):
	global config_transaction_counter
	global state_transaction_counter

	state_transaction_counter = state_transaction_counter + 1
	ts=time.time()
        st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%dT%H:%M:%S')

	rpc="""<get xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">%(filter)s</get>"""%{'filter':filter}
	new_network = lxml.etree.fromstring(lxml.etree.tostring(network))
	nodes = new_network.xpath("node")
	file_name_prefix=str(config_transaction_counter) + "-state-" + str(state_transaction_counter)
	print file_name_prefix
	for node in nodes:
		node_id=node.xpath("node-id")[0].text
		conns[node_id].send(rpc)

	for node in nodes:
		node_id=node.xpath("node-id")[0].text
		result = conns[node_id].receive()
		data = result.xpath("data")[0]
		new_data = lxml.etree.fromstring(lxml.etree.tostring(data))
		#print lxml.etree.tostring(data)
		node.append(new_data)

		file_name=file_name_prefix + "-" + node_id + ".xml"
		data_str=lxml.etree.tostring(new_data)
		#f = open(file_name, "w")
		#f.write(data_str)
		#f.close()
		print file_name + " - start"
		print data_str
		print file_name + " - end"
	new_network = strip_namespaces(new_network)

	return new_network


def copy_config(conn, config):
	rpc ="""
<copy-config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
 <target>
  <candidate/>
 </target>
 <source>
  %(config)s
 </source>
</copy-config>
""" % {'config':config}
	result=conn.rpc(rpc)
	ok=result.xpath('ok')
	if(len(ok)!=1):
		print(rpc)
		print(lxml.etree.tostring(result))
		assert(0)
	return

def edit_config(conn, config):
	rpc ="""
<edit-config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
 <default-operation>merge</default-operation>
 <target>
  <candidate/>
 </target>
  %(config)s
</edit-config>
""" % {'config':config}
	result=conn.rpc(rpc)
	ok=result.xpath('ok')
	if(len(ok)!=1):
		print(rpc)
		print(lxml.etree.tostring(result))
		assert(0)
	print(rpc)
	print(lxml.etree.tostring(result))
	return

def network_commit(conns):
	global config_transaction_counter
	global config_transaction_timestamp_started
	global config_transaction_timestamp_completed
	global state_transaction_counter

	state_transaction_counter = 0
	config_transaction_counter = config_transaction_counter + 1

	rpc='''
<get-config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <source>
    <candidate/>
    </source>
    <filter type="xpath" select="/"/>
</get-config>
'''

	data_str={}
	for conn_id in conns:
		result = conns[conn_id].rpc(rpc)
		data = result.xpath("./data")[0]
		new_data = lxml.etree.fromstring(lxml.etree.tostring(data))
		#file_name=st + "-config" + "-" + conn_id + ".xml"
		file_name=str(config_transaction_counter)+ "-config" + "-" + conn_id + ".xml"
		data_str[conn_id]=lxml.etree.tostring(data)
		#f = open(file_name, "w")
		#f.write(data_str[conn_id])
		#f.close()
		print file_name + " - start"
		print(data_str[conn_id])
		print file_name + " - end"

	config_transaction_timestamp_started=time.time()
	timestamp_started = datetime.datetime.fromtimestamp(config_transaction_timestamp_started).strftime('%Y-%m-%dT%H:%M:%S')
	print "Transaction " + str(config_transaction_counter) + " started: " + timestamp_started

	rpc="""<commit/>"""
	for conn_id in conns:
		conns[conn_id].send(rpc)
	for conn_id in conns:
		result = conns[conn_id].receive()
		ok=result.xpath('ok')
		if(len(ok)!=1):
			print(data_str[conn_id])
			print(rpc)
			print(lxml.etree.tostring(result))
			assert(0)

	config_transaction_timestamp_completed=time.time()
        timestamp_completed = datetime.datetime.fromtimestamp(config_transaction_timestamp_completed).strftime('%Y-%m-%dT%H:%M:%S')
	print "Transaction " + str(config_transaction_counter) + " completed: " + timestamp_completed

	return

def parse_network_links(network_xml):

	link_index=0
	links = network_xml.xpath('link')
	mylinks={}
	for link in links:
		link_id= link.xpath('link-id')[0].text
		source_node = link.xpath('source/source-node')[0].text
		source_tp = link.xpath('source/source-tp')[0].text
		dest_node = link.xpath('destination/dest-node')[0].text
		dest_tp = link.xpath('destination/dest-tp')[0].text

		#print("[%(link_index)d] link-id=%(link_id)s, source-node=%(source_node)s, source-tp=%(source_tp)s, dest-node=%(dest_node)s, dest-tp=%(dest_tp)s" % {'link_index':link_index,'link_id':link_id,'source_node':source_node,'source_tp':source_tp,'dest_node':dest_node,'dest_tp':dest_tp} )
		link_index+=1
		link_type = namedtuple('link', ['source_node', 'source_tp', 'dest_node', 'dest_tp'])
		mylinks[link_id]=link_type(source_node=source_node, source_tp=source_tp, dest_node=dest_node, dest_tp=dest_tp)
	return mylinks

def parse_network_interface(interface_xml):

	interface_variables=[]
	statistics_xml=interface_xml.xpath("statistics")
	if(len(statistics_xml)==0):
		return None
	assert(len(statistics_xml)==1)

	#dynamic type
	for counter_xml in statistics_xml[0]:
		#TODO skip non-counter objects
		interface_variables.append(counter_xml.tag.replace("-","_"))

	interface=namedtuple('interface', interface_variables)
	

	for v in interface_variables:
		xml_leaf=interface_xml.xpath("statistics/"+v.replace("_", "-"))
		if(xml_leaf!=None and len(xml_leaf)==1):
			setattr(interface,v,long(xml_leaf[0].text))
		else:
			setattr(interface,v,None)

	return interface

def parse_network_nodes(network_xml):
	network = {}

	nodes = network_xml.xpath('node')
	for node in nodes:
		node_id = node.xpath('node-id')[0].text
		interfaces = node.xpath("data/interfaces-state/interface")
		network[node_id]={}
		for interface in interfaces:
			name=interface.xpath('name')[0].text
			network[node_id][name]={}
			network[node_id][name]=parse_network_interface(interface)

	return network


def get_counter_delta(counter_before, counter_after):
	if(counter_before==None or counter_after==None):
		return None
	counter_delta=counter_after-counter_before
	return counter_delta

def get_network_counters_delta_interface(if_before, if_after):

	before=parse_network_interface(if_before)
	after=parse_network_interface(if_after)
	interface=before
	for v in dir(interface):
		if not v[0].startswith('_') and not v=='count' and not v=='index':
			setattr(interface,v,get_counter_delta(getattr(before,v),getattr(after,v)))
	return interface

def get_network_counters_delta(before, after):
	network = {}

	nodes = before.xpath('node')
	for node in nodes:
		node_id = node.xpath('node-id')[0].text
		names = node.xpath("data/interfaces-state/interface/name")
		network[node_id]={}
		for name in names:
			interface_before = before.xpath("node[node-id='"+ node_id + "']/data/interfaces-state/interface[name='"+name.text+"']")[0]
			interface_after = after.xpath("node[node-id='"+ node_id + "']/data/interfaces-state/interface[name='"+name.text+"']")[0]
			network[node_id][name.text]={}
			network[node_id][name.text]=get_network_counters_delta_interface(interface_before, interface_after)

	return network
