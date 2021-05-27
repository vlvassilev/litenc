#!/usr/bin/python

from lxml import etree
import time
import sys, os
import argparse
import tntapi
import yangrpc
from yangcli import yangcli
sys.path.append("../common")
from rfc2544 import trial

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network",
	"nt":"urn:ietf:params:xml:ns:yang:ietf-network-topology"}

args=None


def main():
	print("""
#Description: RFC2544 trial run
#Procedure:
#1 - Connect to network specified in the configuration.
#2 - Generate test trial traffic with the specified parameters.
#3 - Wait for the --test-time period.
#4 - Read counter statistics and analyzer state and write a report.
""")
def main():

	global args
	parser = argparse.ArgumentParser()
	parser.add_argument("--config", help="Path to the network configuration *.xml file defining the configuration according to ietf-networks, ietf-networks-topology and netconf-node models e.g. ../networks.xml")
	parser.add_argument('--test-time', default="60",help="Test time for traffic generation in seconds.")
	parser.add_argument('--frame-size', default="64",help="Frame size.")
	parser.add_argument('--interframe-gap', default="20",help="Interframe gap.")
	parser.add_argument('--interburst-gap', default="20",help="Interburst gap.")
	parser.add_argument('--frames-per-burst', default="0",help="Frames per burst.")
	parser.add_argument('--src-node', default=[],help="Transmitting node.")
	parser.add_argument('--src-node-interface', default=[],help="Transmitting node interface e.g. eth0.")
	parser.add_argument('--dst-node', default=[],help="Receiving node.")
	parser.add_argument('--dst-node-interface', default=[],help="Receiving node interface e.g. eth0.")
	parser.add_argument('--src-mac-address', default="01:23:45:67:89:AB",help="Source MAC address.")
	parser.add_argument('--dst-mac-address', default="01:23:45:67:89:AC",help="Destination MAC address.")
	parser.add_argument('--frame-data', default=[],help="Hex string frame data.")
	parser.add_argument('--testframe-type', default="dynamic",help="Type of generated testframe.")
	args = parser.parse_args()

	tree=etree.parse(args.config)
	network = tree.xpath('/nc:config/nd:networks/nd:network', namespaces=namespaces)[0]

	conns = tntapi.network_connect(network)
	yconns = tntapi.network_connect_yangrpc(network)
	mylinks = tntapi.parse_network_links(network)

	assert(conns != None)
	assert(yconns != None)

	(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average) = trial(network, conns, yconns, test_time=int(args.test_time), frame_size=long(args.frame_size), interframe_gap=long(args.interframe_gap), interburst_gap=long(args.interburst_gap), frames_per_burst=long(args.frames_per_burst), src_node=args.src_node, src_node_interface=args.src_node_interface, dst_node=args.dst_node, dst_node_interface=args.dst_node_interface, src_mac_address=args.src_mac_address, dst_mac_address=args.dst_mac_address, frame_data=args.frame_data, testframe_type=args.testframe_type)
	print("Test time:                      %8u"%(int(args.test_time)))
	print("Generated packets:              %8u"%(generated_pkts))
	print("Received  packets:              %8u"%(rx_testframe_pkts))
	#print("Generated octets MB/s:          %8f"%(generated_pkts*float(args.frame_size)/(test_time*1024*1024))
	print("Lost packets:                   %8u"%(generated_pkts-rx_testframe_pkts))
	print("Lost packets percent:           %2.6f"%(100*float(generated_pkts-rx_testframe_pkts)/generated_pkts))
	if(sequence_errors != None):
		print("Sequence errors:                %8u"%(sequence_errors))
		print("Sequence errors percent:        %2.6f"%(100*float(sequence_errors)/generated_pkts))
	if(latency_min != None and rx_testframe_pkts>0):
		print("Latency Min[nanoseconds]:       %8u"%(latency_min))
		print("Latency Max[nanoseconds]:       %8u"%(latency_max))
	else:
		print("Latency Min[nanoseconds]:       NA")
		print("Latency Max[nanoseconds]:       NA")

	return 0

sys.exit(main())
