#!/usr/bin/python

from lxml import etree
import time
import math
import sys, os
import subprocess
import argparse
import tntapi
import yangrpc
from yangcli import yangcli
sys.path.append("../common")
from trial import trial

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network",
	"nt":"urn:ietf:params:xml:ns:yang:ietf-network-topology"}

args=None


def main():

	global args
	parser = argparse.ArgumentParser()
	parser.add_argument("--config", help="Path to the netconf configuration *.xml file defining the configuration according to ietf-networks, ietf-networks-topology and netconf-node models e.g. ../networks.xml")
	parser.add_argument('--test-time', default="6",help="Test time for traffic generation in seconds.")
	parser.add_argument('--description', default="test",help="Test name e.g. Loopback Spark-V2.")
	parser.add_argument('--frame-size', default="64",help="Frame size.")
	parser.add_argument('--interframe-gap', default="20",help="Interframe gap.")
	parser.add_argument('--interburst-gap', default="20",help="Interburst gap.")
	parser.add_argument('--frames-per-burst', default="0",help="Frames per burst.")
	parser.add_argument('--src-node', default=[],help="Transmitting node.")
	parser.add_argument('--src-node-interface', default=[],help="Transmitting node port.")
	parser.add_argument('--dst-node', default=[],help="Receiving node.")
	parser.add_argument('--dst-node-interface', default=[],help="Receiving node port.")
	parser.add_argument('--src-mac-address', default="01:23:45:67:89:AB",help="Source MAC address.")
	parser.add_argument('--dst-mac-address', default="01:23:45:67:89:AC",help="Destination MAC address.")
	parser.add_argument('--src-ipv4-address', default="192.168.0.1",help="Source ipv4 address.")
	parser.add_argument('--dst-ipv4-address', default="192.168.0.2",help="Destination ipv4 address.")
	parser.add_argument('--src-ipv4-udp-port', default="",help="Source ipv4 address.")
	parser.add_argument('--dst-ipv4-udp-port', default="7",help="Destination ipv4 address.")
	parser.add_argument('--ipv4-ttl', default="10",help="ipv4 TTL field.")
	parser.add_argument('--frame-data', default=[],help="Hex string frame data.")
	parser.add_argument('--testframe-type', default="dynamic",help="Type of generated testframe.")
	parser.add_argument('--speed', default="1000000000",help="Maximum interface speed in bits per second e.g 1000000000 for 1Gb Ethernet interface.")
	parser.add_argument('--trial-time', default="2",help="Time each trial takes in seconds.")
	args = parser.parse_args()

	tree=etree.parse(args.config)
	network = tree.xpath('/nc:config/nd:networks/nd:network', namespaces=namespaces)[0]

	conns = tntapi.network_connect(network)
	yconns = tntapi.network_connect_yangrpc(network)
	mylinks = tntapi.parse_network_links(network)

	assert(conns != None)
	assert(yconns != None)

	print("#=RFC2544 Benchmark - %s="%(args.description))
	print("#==Frame size %s octets==", args.frame_size)

	frame_data = subprocess.check_output(("traffic-generator-make-testframe --frame-size=%(frame_size)s --dst-mac-address=%(dst_mac_address)s --src-mac-address=%(src_mac_address)s --src-ipv4-address=%(src_ipv4_address)s --ipv4-ttl=%(ipv4_ttl)s --src-ipv4-udp-port=49184 --dst-ipv4-address=%(dst_ipv4_address)s --dst-ipv4-udp-port=%(dst_ipv4_udp_port)s"%{'frame_size':args.frame_size, 'dst_mac_address':args.dst_mac_address, 'src_mac_address':args.src_mac_address, 'src_ipv4_address':args.src_ipv4_address, 'ipv4_ttl':args.ipv4_ttl, 'dst_ipv4_address':args.dst_ipv4_address, 'dst_ipv4_udp_port':args.dst_ipv4_udp_port}).split(' '))

	print frame_data

	speed=int(args.speed)
	interframe_gap=int(args.interframe_gap)
	frame_size=int(args.frame_size)

	# Throughtput search
	print("#===Throughput===")
	pps_top = (float)(speed/8)/(interframe_gap+frame_size)
	pps_bottom = 1.0
	pps_high = pps_top
	pps_low = pps_bottom
	pps = pps_high

	i=0
	while(i<3):
		interframe_gap = ((speed/8) - frame_size*(pps))/(pps)
		interframe_gap = math.ceil(interframe_gap)

		pps = (float)(speed/8) / (frame_size+interframe_gap)
		print ("%d %f pps, %d ifg ... "%(i, pps, interframe_gap))
		(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average) = trial(network, conns, yconns, test_time=int(args.test_time), frame_size=long(args.frame_size), interframe_gap=interframe_gap, interburst_gap=0, frames_per_burst=0, src_node=args.src_node, src_node_interface=args.src_node_interface, dst_node=args.dst_node, dst_node_interface=args.dst_node_interface, src_mac_address=args.src_mac_address, dst_mac_address=args.dst_mac_address, frame_data=frame_data, testframe_type=args.testframe_type)
		if(rx_testframe_pkts == generated_pkts):
			ok = True
		else:
			ok = False

		print ("#%d %f pps, %d ifg ... %d / %d"%(i, pps, interframe_gap, rx_testframe_pkts, generated_pkts))

		if(ok):
			if(abs(pps_high - pps)<1):
				break
			else:
				pps_low = pps
		else:
			pps_high = pps

		pps = pps_low + (pps_high-pps_low)/2

		i = i + 1
		

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

	#TODO
	print("#===Latency===")
	print("#1 %d ns"%(latency_max))
	print("#===Frame loss rate===")
	print("#===Back to back frames===")
	return 0

sys.exit(main())
