#!/usr/bin/python

from lxml import etree
import time
import sys, os
import argparse
import tntapi
import yangrpc
from yangcli import yangcli
sys.path.append("../common")

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network",
	"nt":"urn:ietf:params:xml:ns:yang:ietf-network-topology"}

args=None

def get_delta_counter(before,after,node_name,inst_id_xpath):
	return long(after.xpath("node[node-id='"+node_name+"']/data/"+inst_id_xpath)[0].text) - long(before.xpath("node[node-id='"+node_name+"']/data/"+inst_id_xpath)[0].text)

def is_interface_test_enabled(node_id,tp_id):
	global args
	match=False
	for interface in args.interfaces:
		x=interface.split('.')
		if(x[0]==node_id and x[1]==tp_id):
			match=True
			break
	return match
def get_traffic_stats(dst_node, dst_node_interface, src_node, src_node_interface, before, after, delta, my_test_time, frame_size, interframe_gap, frames_per_burst, interburst_gap, total_frames):

	global args

	before=tntapi.strip_namespaces(before)
	after=tntapi.strip_namespaces(after)

	#generated_octets=1.0*delta[src_node][src_node_interface].out_octets
	#generated_pkts=generated_octets/(frame_size-4)
	generated_pkts = total_frames
	generated_octets = total_frames*frame_size

	#assert(delta[src_node][src_node_interface].out_unicast_pkts==generated_pkts)

	#assert(generated_octets>0)
	print("generated_octets="+str(generated_octets))
	testframe_pkts_nodes = after.xpath("""node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/testframe-pkts"""%(dst_node, dst_node_interface))
	if(len(testframe_pkts_nodes) == 1):
		rx_testframe_pkts=1.0*get_delta_counter(before,after,dst_node,"""/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/testframe-pkts"""%(dst_node_interface))
#		assert(rx_testframe_pkts>0)
	else:
		rx_testframe_pkts=None
		assert(0)

	sequence_errors_nodes = after.xpath("""node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/sequence-errors"""%(dst_node, dst_node_interface))
	if(len(sequence_errors_nodes) == 1):
		sequence_errors=get_delta_counter(before,after,dst_node,"""/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/sequence-errors"""%(dst_node_interface))
	else:
		sequence_errors=None


	rx_in_pkts=1.0*long(after.xpath("""node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/pkts"""%(dst_node, dst_node_interface))[0].text)

	latency_nodes = after.xpath("""node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency"""%(dst_node, dst_node_interface))
	if(len(latency_nodes) == 1):
		latency_min = long(after.xpath("node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency/min"%(dst_node, dst_node_interface))[0].text)
		latency_max = long(after.xpath("node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency/max"%(dst_node, dst_node_interface))[0].text)
		#latency_average = long(after.xpath("node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency/average"%(dst_node, dst_node_interface))[0].text)
		latency_average=None
	else:
		latency_min=None
		latency_max=None
		latency_average=None

 
	return (rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average)

def trial(network, conns, yconns, test_time=60, frame_size=1500, interframe_gap=20, interburst_gap=0, frames_per_burst=0, src_node=[], src_node_interface=[], dst_node=[], dst_node_interface=[], src_mac_address=[], dst_mac_address=[], frame_data=[], testframe_type=[]):
	global args
	filter ="" #"""<filter type="xpath" select="/*[local-name()='interfaces-state' or local-name()='interfaces']/interface/*[local-name()='traffic-analyzer' or local-name()='oper-status' or local-name()='statistics' or local-name()='speed']"/>"""

	config_idle={}
	print(dst_node)
	result=yangcli(yconns[dst_node],"""replace /interfaces/interface[name='%(name)s'] -- type=ethernetCsmacd"""%{'name':dst_node_interface})
	ok = result.xpath('./ok')
	assert(len(ok)==1)
	ok=yangcli(yconns[src_node],"""replace /interfaces/interface[name='%(name)s'] -- type=ethernetCsmacd"""%{'name':src_node_interface}).xpath('./ok')
	assert(len(ok)==1)

	tntapi.network_commit(conns)

	ok=yangcli(yconns[dst_node],"""create /interfaces/interface[name='%(name)s']/traffic-analyzer"""%{'name':dst_node_interface}).xpath('./ok')
	assert(len(ok)==1)

	tntapi.network_commit(conns)

	if(frames_per_burst>0):
		my_burst_config="""frames-per-burst=%(frames-per-burst)d interburst-gap=%(interburst-gap)d""" % {'frames-per-burst':frames_per_burst,'interburst-gap':interburst_gap-8}
	else:
		my_burst_config=""

	generator_direction_suffix=''
	analyzer_direction_suffix=''

	state_before = tntapi.network_get_state(network, conns, filter=filter)
	state_before_wo_ns=tntapi.strip_namespaces(state_before)
	#speed=1000000000 # 1Gb
	speed = long(state_before_wo_ns.xpath("node[node-id='%s']/data/interfaces-state/interface[name='%s']/speed"%(src_node, src_node_interface))[0].text)

	if(frames_per_burst == 0):
		total_frames = test_time*speed/((interframe_gap+frame_size)*8)
	else:
		total_frames = frames_per_burst*test_time*speed/(((frames_per_burst-1)*interframe_gap+frames_per_burst*frame_size+interburst_gap)*8)

	testframe = ""
	if(testframe_type != []):
		testframe = "testframe-type=%s" % testframe_type
	print """create /interfaces/interface[name="%(name)s"]/traffic-generator -- frame-size=%(frame-size)d interframe-gap=%(interframe-gap)d total-frames=%(total-frames)s %(burst)s frame-data=%(frame-data)s %(testframe)s""" % {'name':src_node_interface,'frame-size':frame_size, 'interframe-gap':interframe_gap, 'burst':my_burst_config, 'total-frames':total_frames, 'frame-data':frame_data, 'testframe':testframe}
	ok=yangcli(yconns[src_node],"""create /interfaces/interface[name="%(name)s"]/traffic-generator -- frame-size=%(frame-size)d interframe-gap=%(interframe-gap)d total-frames=%(total-frames)s %(burst)s frame-data=%(frame-data)s %(testframe)s""" % {'name':src_node_interface,'frame-size':frame_size, 'interframe-gap':interframe_gap, 'burst':my_burst_config, 'total-frames':total_frames, 'frame-data':frame_data, 'testframe':testframe}).xpath('./ok')
	assert(len(ok)==1)


	state_before = tntapi.network_get_state(network, conns, filter=filter)
	tntapi.network_commit(conns)

	print("Waiting " + str(test_time) + " sec. ..." )
	time.sleep(test_time+1)

	print("Stopping generators ...")
	ok=yangcli(yconns[src_node],"""delete /interfaces/interface[name='%(name)s']/traffic-generator"""%{'name':src_node_interface}).xpath('./ok')
	assert(len(ok)==1)

	tntapi.network_commit(conns)
	print("Done.")

	state_after = tntapi.network_get_state(network, conns, filter=filter)

	t1 = tntapi.parse_network_nodes(state_before)
	t2 = tntapi.parse_network_nodes(state_after)
	delta = tntapi.get_network_counters_delta(state_before,state_after)

	tntapi.print_state_ietf_interfaces_statistics_delta(network, state_before, state_after)

	(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average)=get_traffic_stats(dst_node, dst_node_interface, src_node, src_node_interface, state_before, state_after, delta, test_time, frame_size, interframe_gap, frames_per_burst, interburst_gap, total_frames)

	print("Disabling analyzer.")
	ok=yangcli(yconns[dst_node],"""delete /interfaces/interface[name='%(name)s']/traffic-analyzer%(analyzer-direction-suffix)s"""%{'name':dst_node_interface, 'analyzer-direction-suffix':analyzer_direction_suffix}).xpath('./ok')
	assert(len(ok)==1)

	tntapi.network_commit(conns)

	return 	(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average)


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
	parser.add_argument('--testframe-type', default=[],help="Type of generated testframe.")
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
