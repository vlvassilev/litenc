#!/usr/bin/python
import lxml

#Helper function demonstration the automation of common printouts.

# Function: print_state_ietf_interfaces_statistics_delta
# Description: All counters under /interfaces-state/interface/statistics are
# compared and printed in case the value has increased.
# Example output:
# analyzer=1;local=2;remote=3;
# ge0=1;ge1=2;ge15=3;ge2=4;ge3=5;ge4=6;ge5=7;ge6=8;ge7=9;ge8=10;ge9=11;xe0=12;
# tx_oversize_frames(remote,ge1)=1707397;
# out_octets(remote,ge0)=28068236658;
# out_pkts(remote,ge0)=1707937;
# out_unicast_pkts(remote,ge0)=1707937;
# ...
# The output is compatible with Matlab/octave CLI

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network",
	"nt":"urn:ietf:params:xml:ns:yang:ietf-network-topology",
	"if":"urn:ietf:params:xml:ns:yang:ietf-interfaces"}

def print_state_ietf_interfaces_statistics_delta(network, before, after):
	import tntapi
	print("Printing state ...")
	t1 = tntapi.parse_network_nodes(before)
	t2 = tntapi.parse_network_nodes(after)
	delta = tntapi.get_network_counters_delta(before,after)

	i=1
	line=""
	node_dict=dict()
	tp_dict=dict()
        nodes = network.xpath('nd:node',namespaces=namespaces)
	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		node_dict[node_id]=1
		termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
		for termination_point in termination_points:
			tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
			if tp_id not in tp_dict:
				tp_dict[tp_id] = 1

	line=""
	i=1
	for node in sorted(node_dict):
		line=line+"%s=%d;"%(node,i)
		i=i+1
	print(line) #e.g. "local=1;remote=2;analyzer=3;"

	line=""
	i=1
	for tp in sorted(tp_dict):
		line=line+"%s=%d;"%(tp,i)
		i=i+1
	print(line) #e.g. #"xe0=1;xe1=2;ge0=3;"


	#print all non-zero deltas
	for node in node_dict:
		for if_name in tp_dict.keys():
			if if_name not in delta[node]:
				continue
			interface = delta[node][if_name]
			for v in dir(interface):
				if not v[0].startswith('_') and not v=='count' and not v=='index':
					value = getattr(interface,v)
					if(value!=None and value!=0):
						print v + "(" + node + ","+ if_name + ")=" + str(value) + ";"
