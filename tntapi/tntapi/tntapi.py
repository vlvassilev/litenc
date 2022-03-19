#!/usr/bin/python
import lxml
import time
import datetime
import sys, os
import argparse
from collections import namedtuple
from copy import deepcopy
#from tntapi_netconf_session_ncclient import netconf_session_ncclient
from tntapi_netconf_session_litenc import netconf_session_litenc
from tntapi_strip_namespaces import strip_namespaces
from tntapi_print_state import print_state_ietf_interfaces_statistics_delta

config_transaction_counter = 0
config_transaction_timestamp_started = None
config_transaction_timestamp_completed = None
state_transaction_counter = 0
namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network",
	"nt":"urn:ietf:params:xml:ns:yang:ietf-network-topology",
	"netconf-node":"urn:tntapi:netconf-node"}

yangcli_supported=False
try:
	import yangrpc
	from yangcli import yangcli as yangcli_imp
	#print("yangcli supported.")
	yangcli_supported=True
except ImportError:
	print("yangcli not supported.")

def controller_connect(address, ncport, user, password, pub_key, priv_key, misc_args):
	#TODO - connect to controller retrieve topology and emulate direct conns
	network={}
	conns={}
	return network,conns

def controller_connect_yangrpc(address, ncport, user, password, pub_key, priv_key, misc_args):
	#TODO - connect to controller retrieve topology and emulate direct yangrpc conns
	network={}
	conns={}
	return network,conns

def network_connect(network):

	conns={}
	network_id = network.xpath('nd:network-id', namespaces=namespaces)
	print("Connecting to network: " + network_id[0].text)
	nodes = network.xpath('nd:node', namespaces=namespaces)
	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		server = node.xpath('netconf-node:netconf-connect-params/netconf-node:server', namespaces=namespaces)[0].text
		user =node.xpath('netconf-node:netconf-connect-params/netconf-node:user', namespaces=namespaces)[0].text
		if(1==len(node.xpath('netconf-node:netconf-connect-params/netconf-node:password', namespaces=namespaces))):
			password=node.xpath('netconf-node:netconf-connect-params/netconf-node:password', namespaces=namespaces)[0].text
		else:
			password=None
		ncport = node.xpath('netconf-node:netconf-connect-params/netconf-node:ncport', namespaces=namespaces)[0].text

		print("Connect to " + node_id +" (server=%(server)s user=%(user)s) password=%(password)s ncport=%(ncport)s:" % {'server':server, 'user':user, 'password':password, 'ncport':ncport})
		conns[node_id] = netconf_session_litenc(host=server,port=int(ncport),username=user,password=password,timeout=100)

		if conns[node_id] == None:
			print("FAILED connect")
			return(None)
		else:
			print("OK")
	return conns

def network_connect_yangrpc(network):

	yconns={}
	if(yangcli_supported!=True):
		return network_connect(network)
	network_id = network.xpath('nd:network-id', namespaces=namespaces)
	print("Connecting to YANG network: " + network_id[0].text)
	nodes = network.xpath('nd:node', namespaces=namespaces)
	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		server = node.xpath('netconf-node:netconf-connect-params/netconf-node:server', namespaces=namespaces)[0].text
		user =node.xpath('netconf-node:netconf-connect-params/netconf-node:user', namespaces=namespaces)[0].text
		if(1==len(node.xpath('netconf-node:netconf-connect-params/netconf-node:password', namespaces=namespaces))):
			password=node.xpath('netconf-node:netconf-connect-params/netconf-node:password', namespaces=namespaces)[0].text
		else:
			password=None
		ncport = node.xpath('netconf-node:netconf-connect-params/netconf-node:ncport', namespaces=namespaces)[0].text

		print("Connect to YANG device " + node_id +" (server=%(server)s user=%(user)s) password=%(password)s ncport=%(ncport)s:" % {'server':server, 'user':user, 'password':password, 'ncport':ncport})
		yconns[node_id] = yangrpc.connect(server, int(ncport), user, password, os.getenv('HOME')+"/.ssh/id_rsa.pub", os.getenv('HOME')+"/.ssh/id_rsa", "--dump-session=nc-session-")

		if yconns[node_id] == None:
			print("FAILED connect")
			return(None)
		else:
			print("OK")
	return yconns

def network_get_state(network, conns, filter=""):
	global config_transaction_counter
	global state_transaction_counter

	#state_transaction_counter = state_transaction_counter + 1
	ts=time.time()
        st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%dT%H:%M:%S')

	new_network = lxml.etree.fromstring(lxml.etree.tostring(network))
	nodes = new_network.xpath("nd:node", namespaces=namespaces)
	assert(len(nodes)>0)
	file_name_prefix=str(config_transaction_counter) + "-state-" + str(state_transaction_counter)
	print(file_name_prefix)
	for node in nodes:
		node_id=node.xpath("nd:node-id", namespaces=namespaces)[0].text
		my_filter=""
		if(filter==""):
			my_filter_elements=node.xpath("netconf-node:netconf-get-filter/nc:filter", namespaces=namespaces)
			if len(my_filter_elements)==1:
				my_filter=lxml.etree.tostring(my_filter_elements[0])
		else:
			my_filter=filter
		rpc="""<get xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">%(filter)s</get>"""%{'filter':my_filter}
		conns[node_id].send(rpc)

	for node in nodes:
		node_id=node.xpath("nd:node-id", namespaces=namespaces)[0].text
		datas=node.xpath("netconf-node:data", namespaces=namespaces)
		assert(len(datas)<=1)
		if(len(datas)==1):
			data=datas[0]
			data.getparent().remove(data)
		result = conns[node_id].receive()
		data = result.xpath("nc:data", namespaces=namespaces)[0]
		new_data = lxml.etree.fromstring(lxml.etree.tostring(data))

		netconf_node_data=lxml.etree.Element("{urn:tntapi:netconf-node}data", nsmap=namespaces)
		node.append(netconf_node_data)
		for child in new_data:
			netconf_node_data.append( deepcopy(child) )

		file_name=file_name_prefix + "-" + node_id + ".xml"
		data_str=lxml.etree.tostring(new_data)
		#f = open(file_name, "w")
		#f.write(data_str)
		#f.close()
		print(file_name + " - start")
		print(data_str)
		print(file_name + " - end")

	return new_network

def network_get_config(network, conns, filter=""):
	global config_transaction_counter
	global state_transaction_counter

	#state_transaction_counter = state_transaction_counter + 1
	ts=time.time()
        st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%dT%H:%M:%S')

	rpc="""<get-config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">%(filter)s<source><running/></source></get-config>"""%{'filter':filter}
	new_network = lxml.etree.fromstring(lxml.etree.tostring(network))
	nodes = new_network.xpath("nd:node", namespaces=namespaces)
	assert(len(nodes)>0)
	file_name_prefix=str(config_transaction_counter) + "-config-" + str(state_transaction_counter)
	print(file_name_prefix)
	for node in nodes:
		node_id=node.xpath("nd:node-id", namespaces=namespaces)[0].text
		configs=node.xpath("netconf-node:config", namespaces=namespaces)
		assert(len(configs)<=1)
		if(len(configs)==1):
			config=configs[0]
			config.getparent().remove(config)
		conns[node_id].send(rpc)

	for node in nodes:
		node_id=node.xpath("nd:node-id", namespaces=namespaces)[0].text

		result = conns[node_id].receive()
		print(result.tag)
		print(lxml.etree.tostring(result))
		data = result.xpath("nc:data", namespaces=namespaces)[0]
		new_data = lxml.etree.fromstring(lxml.etree.tostring(data))
		netconf_node_config=lxml.etree.Element("{urn:tntapi:netconf-node}config", nsmap=namespaces)
		node.append(netconf_node_config)
		for child in new_data:
			netconf_node_config.append( deepcopy(child) )

		file_name=file_name_prefix + "-" + node_id + ".xml"
		data_str=lxml.etree.tostring(new_data)
		#f = open(file_name, "w")
		#f.write(data_str)
		#f.close()
		print(file_name + " - start")
		print(data_str)
		print(file_name + " - end")

	return new_network

def yangcli(conn, cmd_line):
	if(yangcli_supported):
		return yangcli_imp(conn, cmd_line, strip_namespaces=False)
	else:
		#yangcli-less developers in case the server supports yangcli-to-rpc
		myns = namespaces
		myns.update({"yangcli-to-rpc":"http://yuma123.org/ns/yangcli-to-rpc"})
		yangcli_to_rpc="""
<yangcli-to-rpc xmlns="http://yuma123.org/ns/yangcli-to-rpc">
  <cmd>%s</cmd>
</yangcli-to-rpc>
"""%(cmd_line)
		result=conn.rpc(yangcli_to_rpc)
		rpc_xml=result.xpath('yangcli-to-rpc:rpc/child::*', namespaces=myns)
		assert(len(rpc_xml)==1)
		return conn.rpc(lxml.etree.tostring(rpc_xml[0]))

def yangcli_ok_script(yconn, yangcli_script):
	for line in yangcli_script.splitlines():
		line=line.strip()
		if not line:
			continue
		print("Executing: %s"%(line))
		result = yangcli(yconn, line)
		ok=result.xpath('./nc:ok', namespaces=namespaces)
		if(len(ok)!=1):
			print(lxml.etree.tostring(result))
			assert(0)

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
	ok=result.xpath('nc:ok', namespaces=namespaces)
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
	ok=result.xpath('nc:ok', namespaces=namespaces)
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
		data = result.xpath("./nc:data", namespaces=namespaces)[0]
		new_data = lxml.etree.fromstring(lxml.etree.tostring(data))
		#file_name=st + "-config" + "-" + conn_id + ".xml"
		file_name=str(config_transaction_counter)+ "-config" + "-" + conn_id + ".xml"
		data_str[conn_id]=lxml.etree.tostring(data)
		#f = open(file_name, "w")
		#f.write(data_str[conn_id])
		#f.close()
		print(file_name + " - start")
		print(data_str[conn_id])
		print(file_name + " - end")

	config_transaction_timestamp_started=time.time()
	timestamp_started = datetime.datetime.fromtimestamp(config_transaction_timestamp_started).strftime('%Y-%m-%dT%H:%M:%S')
	print("Transaction " + str(config_transaction_counter) + " started: " + timestamp_started)

	rpc="""<commit/>"""
	for conn_id in conns:
		conns[conn_id].send(rpc)
	for conn_id in conns:
		result = conns[conn_id].receive()
		ok=result.xpath('nc:ok', namespaces=namespaces)
		if(len(ok)!=1):
			print(data_str[conn_id])
			print(rpc)
			print(lxml.etree.tostring(result))
			assert(0)

	config_transaction_timestamp_completed=time.time()
        timestamp_completed = datetime.datetime.fromtimestamp(config_transaction_timestamp_completed).strftime('%Y-%m-%dT%H:%M:%S')
	print("Transaction " + str(config_transaction_counter) + " completed: " + timestamp_completed)

	return

def parse_network_links(network_xml):

	link_index=0
	links = network_xml.xpath('nt:link', namespaces=namespaces)
	mylinks={}
	for link in links:
		link_id= link.xpath('nt:link-id', namespaces=namespaces)[0].text
		source_node = link.xpath('nt:source/nt:source-node', namespaces=namespaces)[0].text
		source_tp = link.xpath('nt:source/nt:source-tp', namespaces=namespaces)[0].text
		dest_node = link.xpath('nt:destination/nt:dest-node', namespaces=namespaces)[0].text
		dest_tp = link.xpath('nt:destination/nt:dest-tp', namespaces=namespaces)[0].text

		#print("[%(link_index)d] link-id=%(link_id)s, source-node=%(source_node)s, source-tp=%(source_tp)s, dest-node=%(dest_node)s, dest-tp=%(dest_tp)s" % {'link_index':link_index,'link_id':link_id,'source_node':source_node,'source_tp':source_tp,'dest_node':dest_node,'dest_tp':dest_tp} )
		link_index+=1
		link_type = namedtuple('link', ['source_node', 'source_tp', 'dest_node', 'dest_tp'])
		mylinks[link_id]=link_type(source_node=source_node, source_tp=source_tp, dest_node=dest_node, dest_tp=dest_tp)
	return mylinks

def parse_network_interface(interface_xml):
	interface_xml=strip_namespaces(interface_xml)
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
	network_xml=strip_namespaces(network_xml)
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
	before=strip_namespaces(before)
	after=strip_namespaces(after)
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

def get_datetime_delta(before, after):
	before=strip_namespaces(before)
	after=strip_namespaces(after)
	network = {}

	nodes = before.xpath('node')
	for node in nodes:
		node_id = node.xpath('node-id')[0].text
		datetime_before=before.xpath("node[node-id='%s']/data/system-state/clock/current-datetime"%(node_id))
		datetime_after=  after.xpath("node[node-id='%s']/data/system-state/clock/current-datetime"%(node_id))
		if(len(datetime_before)==1 and len(datetime_after)==1):
			if(len(datetime_before[0].text)>len('1970-01-01T00:00:00.000000')):
				strptime_fmt_spec='%Y-%m-%dT%H:%M:%S.%f'
				strptime_str_len=len('1970-01-01T00:00:00.000000')
			else:
				strptime_fmt_spec='%Y-%m-%dT%H:%M:%S'
				strptime_str_len=len('1970-01-01T00:00:00')

			dt_before = datetime.datetime.strptime(datetime_before[0].text[:strptime_str_len], strptime_fmt_spec)
			dt_after = datetime.datetime.strptime(datetime_after[0].text[:strptime_str_len],   strptime_fmt_spec)
			period = float((dt_after-dt_before).total_seconds())
			network[node_id]=period
		else:
			network[node_id]=None

	return network
