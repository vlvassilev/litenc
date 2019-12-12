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

test_time=60
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

def validate_traffic_on(node_name, interface_name, before, after, delta, my_test_time, load_percent, frame_size, interframe_gap, frames_per_burst, interburst_gap):

	global test_time
	global args

	print("validate_traffic_on %s"%(interface_name))

	before=tntapi.strip_namespaces(before)
	after=tntapi.strip_namespaces(after)

	speed_bits_per_sec=long(after.xpath("node[node-id='"+node_name+"']/data/interfaces-state/interface[name='"+interface_name+"']/speed")[0].text)
	print "speed(bits/sec)="+str(speed_bits_per_sec)
	print "speed(bytes/sec)="+str(speed_bits_per_sec/8)
	if (args.direction=='ingress'):
		generated_pkts=	1.0*delta[node_name][interface_name].generated_ingress_pkts
		generated_octets=frame_size*generated_pkts
	else:
		generated_octets=1.0*delta[node_name][interface_name].out_octets
		assert(delta[node_name][interface_name].out_multicast_pkts==0)
		assert(delta[node_name][interface_name].out_unicast_pkts>0)
		generated_pkts=generated_octets/frame_size
		assert(delta[node_name][interface_name].out_unicast_pkts==generated_pkts)

	assert(generated_octets>0)
	print("generated_octets="+str(generated_octets))

	if (args.test_internal_loopback=='true'):
		looped_back_octets=1.0*delta[node_name][interface_name].in_octets
		print("looped_back_octets="+str(looped_back_octets))
		assert(looped_back_octets==generated_octets)

	if (args.test_analyzer=='true'):
		if (args.direction=='ingress'):
			analyzed_pkts=1.0*get_delta_counter(before,after,node_name,"""/interfaces/interface[name='%s']/traffic-analyzer-egress/state/testframe-stats/testframe-pkts"""%(interface_name))
		else:
			analyzed_pkts=1.0*get_delta_counter(before,after,node_name,"""/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/testframe-pkts"""%(interface_name))

		print("generated_pkts="+str(generated_pkts))
		print("analyzed_pkts="+str(analyzed_pkts))
		assert(generated_pkts==analyzed_pkts)

	generated_octets_expected=(load_percent*test_time*speed_bits_per_sec/(8*100))
	print("Generated octets per sec="+str(generated_octets/test_time))
	print("Expected octets per sec="+str(generated_octets_expected/test_time))
	ratio=generated_octets/generated_octets_expected
	if(ratio>1):
		print("Generated %(r).4f times MORE: generated=%(g)d and expected=%(e)d"%{'r':ratio, 'g':generated_octets,'e':generated_octets_expected})
		if(ratio>(110.0/100)):
			print("Error: >10% precision deviation.")
	elif(ratio<1):
		print("Generated %(r).4f times LESS: generated=%(g)d and expected=%(e)d"%{'r':1/ratio, 'g':generated_octets,'e':generated_octets_expected})
		if(ratio<(90.0/100)):
			print("Error: >10% precision deviation.")
	else:
		print("Generated EXACTLY: generated=%(g)s and expected=%(e)s"%{'g':generated_octets,'e':generated_octets_expected})

	return float(100*generated_octets/(test_time*speed_bits_per_sec/8))

def validate_traffic_off(node_name, interface_name, before, after, delta, frame_size):
	global args
	print (node_name+"."+interface_name)
	if (args.direction=='ingress'):
		generated_pkts=1.0*delta[node_name][interface_name].generated_ingress_pkts
		generated_octets=frame_size*generated_pkts
	else:
		generated_octets=1.0*delta[node_name][interface_name].out_octets

	generated_octets=1.0*delta[node_name][interface_name].out_octets
	#assert(generated_octets==0)

def validate(network, conns, yconns, inks, load_percent=99, frame_size=1500, interframe_gap=12, frames_per_burst=0, interburst_gap=0):
	global args
	filter ="" #"""<filter type="xpath" select="/*[local-name()='interfaces-state' or local-name()='interfaces']/interface/*[local-name()='traffic-analyzer' or local-name()='oper-status' or local-name()='statistics' or local-name()='speed']"/>"""

	config_idle={}
        nodes = network.xpath('nd:node', namespaces=namespaces)
	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		config=""
		print node_id

		termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
		for termination_point in termination_points:
			tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
			if(not is_interface_test_enabled(node_id,tp_id)):
				continue
			ok=yangcli(yconns[node_id],"""replace /interfaces/interface[name='%(name)s'] -- type=ethernetCsmacd"""%{'name':tp_id}).xpath('./ok')
			assert(len(ok)==1)

	tntapi.network_commit(conns)

	state_before = tntapi.network_get_state(network, conns, filter=filter)
	print("Waiting " + "5" + " sec. ..." )
	time.sleep(5)
	print("Done.")
	state_after = tntapi.network_get_state(network, conns, filter=filter)

	mylinks = tntapi.parse_network_links(state_before)
	t1 = tntapi.parse_network_nodes(state_before)
	t2 = tntapi.parse_network_nodes(state_after)
	delta = tntapi.get_network_counters_delta(state_before,state_after)

	tntapi.print_state_ietf_interfaces_statistics_delta(network, state_before, state_after)

	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
		for termination_point in termination_points:
			tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
			if(not is_interface_test_enabled(node_id,tp_id)):
				continue
			validate_traffic_off(node_id, tp_id, state_before, state_after, delta, frame_size)

	load=float(load_percent)/100
	print "ifg="+str(interframe_gap)

        if(args.test_internal_loopback=="true"):
		print("Enabling internal loopbacks.")
		for node in nodes:
			node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
			termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
			for termination_point in termination_points:
				tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
				if(not is_interface_test_enabled(node_id,tp_id)):
					continue
				ok=yangcli(yconns[node_id],"""merge /interfaces/interface[name='%(name)s'] -- loopback=internal"""%{'name':tp_id}).xpath('./ok')
				assert(len(ok)==1)

		tntapi.network_commit(conns)

        if(args.test_analyzer=="true"):
		print("Enabling analyzer.")
		for node in nodes:
			node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
			termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
			for termination_point in termination_points:
				tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
				if(not is_interface_test_enabled(node_id,tp_id)):
					continue
				if(args.direction=='ingress'):
					ok=yangcli(yconns[node_id],"""create /interfaces/interface[name='%(name)s']/traffic-analyzer-egress"""%{'name':tp_id}).xpath('./ok')
				else:
					ok=yangcli(yconns[node_id],"""create /interfaces/interface[name='%(name)s']/traffic-analyzer"""%{'name':tp_id}).xpath('./ok')
				assert(len(ok)==1)

		tntapi.network_commit(conns)

	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		config=""

		termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
		for termination_point in termination_points:
			tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
			if(not is_interface_test_enabled(node_id,tp_id)):
				continue
			if(frames_per_burst>0):
				my_burst_config="""frames-per-burst=%(frames-per-burst)d interburst-gap=%(interburst-gap)d""" % {'frames-per-burst':frames_per_burst,'interburst-gap':interburst_gap-8}
			else:
				my_burst_config=""

			if(args.direction=='ingress'):
				generator_direction_suffix='-ingress'
				analyzer_direction_suffix='-egress'
			else:
				generator_direction_suffix=''
				analyzer_direction_suffix=''

			ok=yangcli(yconns[node_id],"""create /interfaces/interface[name='%(name)s']/traffic-generator%(generator-direction-suffix)s -- ether-type=%(ether-type)d frame-size=%(frame-size)d interframe-gap=%(interframe-gap)d %(burst)s""" % {'name':tp_id,'generator-direction-suffix':generator_direction_suffix,'frame-size':frame_size,'ether-type':0x1234, 'interframe-gap':interframe_gap-8, 'burst':my_burst_config}).xpath('./ok')
			assert(len(ok)==1)


	state_before = tntapi.network_get_state(network, conns, filter=filter)
        tntapi.network_commit(conns)

	print("Waiting " + str(test_time) + " sec. ..." )
	time.sleep(test_time)

	print("Stopping generators ...")
	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		config=""

		termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
		for termination_point in termination_points:
			tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
			if(not is_interface_test_enabled(node_id,tp_id)):
				continue
			ok=yangcli(yconns[node_id],"""delete /interfaces/interface[name='%(name)s']/traffic-generator%(generator-direction-suffix)s"""%{'name':tp_id,'generator-direction-suffix':generator_direction_suffix}).xpath('./ok')
			assert(len(ok)==1)

	tntapi.network_commit(conns)
	print("Done.")

	state_after = tntapi.network_get_state(network, conns, filter=filter)

	t1 = tntapi.parse_network_nodes(state_before)
	t2 = tntapi.parse_network_nodes(state_after)
	delta = tntapi.get_network_counters_delta(state_before,state_after)

	tntapi.print_state_ietf_interfaces_statistics_delta(network, state_before, state_after)

	load_generated={}
	for node in nodes:
		node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
		termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
		for termination_point in termination_points:
			tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
			if(not is_interface_test_enabled(node_id,tp_id)):
				continue
			load_generated[node_id,tp_id]=validate_traffic_on(node_id, tp_id, state_before, state_after, delta, test_time, load_percent, frame_size, interframe_gap, frames_per_burst, interburst_gap)

        if(args.test_analyzer=="true"):
		print("Disabling analyzer.")
		for node in nodes:
			node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
			termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
			for termination_point in termination_points:
				tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
				if(not is_interface_test_enabled(node_id,tp_id)):
					continue
				ok=yangcli(yconns[node_id],"""delete /interfaces/interface[name='%(name)s']/traffic-analyzer%(analyzer-direction-suffix)s"""%{'name':tp_id, 'analyzer-direction-suffix':analyzer_direction_suffix}).xpath('./ok')
				assert(len(ok)==1)

		tntapi.network_commit(conns)

        if(args.test_internal_loopback=="true"):
		print("Disabling internal loopbacks.")
		for node in nodes:
			node_id = node.xpath('nd:node-id', namespaces=namespaces)[0].text
			termination_points = node.xpath('./nt:termination-point', namespaces=namespaces)
			for termination_point in termination_points:
				tp_id = termination_point.xpath('nt:tp-id', namespaces=namespaces)[0].text
				if(not is_interface_test_enabled(node_id,tp_id)):
					continue
				ok=yangcli(yconns[node_id],"""delete /interfaces/interface[name='%(name)s']/loopback"""%{'name':tp_id}).xpath('./ok')
				assert(len(ok)==1)

		tntapi.network_commit(conns)

	return (load_percent, load_generated)

def display_table(bw_expected, bw_generated):
	print(bw_generated)

	header_line="| Port \ Run    "

	for key in bw_generated.keys():
		header_line=header_line+"|  %3d   "%(key)
	header_line=header_line+"|"

	len(header_line)
	outer_border_line="+"+(len(header_line)-2)*"-"+"+"
	border_line="|"+(len(header_line)-2)*"-"+"|"

	print(outer_border_line)
	print(header_line)
	print(outer_border_line)

	line="| NORM          "
	for key in bw_generated.keys():
		line=line+"| %6.2f "%(bw_expected[key])
	line=line+"|"
	print line

	for key in bw_generated[1].keys():
		print(border_line)
		line="| " +key[0]+"."+key[1]
		line=line + " "*(16-len(line))
		for run in bw_generated.keys():
			line=line+"| %6.2f "%(bw_generated[run][key[0],key[1]])
		print(line+ "|")
	print(outer_border_line)
	return 0

def main():
	print("""
#Description: Automated network interconnect tester self-test
#Procedure:
#1 - Generate maximum traffic load with maximum frame size 98.7% 6+6+2+1500+4 byte packets 7+1+12 byte ifg and verify counters.
#2 - Generate maximum traffic load with minimum frame size 76.19% 6+6+2+46+4 byte packets 7+1+12 byte ifg and verify counters.
#3 - Generate 50% traffic load with maximum frame size 6+6+2+1500+4 byte packets 7+1+12+1498 byte ifg and verify counters.
#4 - Generate 50% traffic load with minimum frame size 6+6+2+46+4 byte packets 7+1+12+44 byte ifg and verify counters.
#5 - Generate 5% traffic load with maximum frame size 6+6+2+1500+4 byte packets 7+1+12+28822 byte ifg and verify counters.
#6 - Generate 50% burst traffic load 6+6+2+1500+4 byte packets 7+1+12 byte ifg, frames-per-burst=10, interburst-gap=7+1+12+14980 and verify counters.
#7 - Generate 5% burst traffic load 6+6+2+1500+4 byte packets 7+1+12 byte ifg, frames-per-burst=10, interburst-gap=7+1+12+288220 and verify counters.
#8 - Generate 10% burst traffic load 6+6+2+1500+4 byte packets 7+1+12+27284 byte ifg, frames-per-burst=2, interburst-gap=7+1+12 and verify counters.
#9 - Generate maximum traffic load with minimum frame size 76.19% traffic load 6+6+2+46+4 byte packets 7+1+12 byte ifg, frames-per-burst=2, interburst-gap=7+1+12 and verify counters.
""")
def main():

	global test_time
	global args
	parser = argparse.ArgumentParser()
	parser.add_argument("--config", help="Path to the netconf configuration *.xml file defining the configuration according to ietf-networks, ietf-networks-topology and netconf-node models e.g. ../networks.xml")
	parser.add_argument("--direction", help="--direction=ingress or --direction=egress")
	parser.add_argument('--interface', action='append', dest='interfaces',default=[],help="Add interface to be tested e.g --interface='foo.ge0 --interface=bar.xe1'")
	parser.add_argument('--test-internal-loopback', help="When direction=='egress' create 'internal' loopback on all interfaces and validate in_octets==out_octets")
	parser.add_argument('--test-analyzer', help="Create traffic-analyzer and measure min and max latency")
	args = parser.parse_args()

	tree=etree.parse(args.config)
	network = tree.xpath('/nc:config/nd:networks/nd:network', namespaces=namespaces)[0]

	conns = tntapi.network_connect(network)
	yconns = tntapi.network_connect_yangrpc(network)
	mylinks = tntapi.parse_network_links(network)

	assert(conns != None)
	assert(yconns != None)

	step=1
	bw_expected={}
	bw_generated={}


	#1 - Generate maximum traffic load with maximum frame size 98.7% 6+6+2+1500+4 byte packets 7+1+12 byte ifg and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 98.7, frame_size=6+6+2+1500+4, interframe_gap=7+1+12)
	step=step+1


	#2 - Generate maximum traffic load with minimum frame size 76.19% 6+6+2+46+4 byte packets 7+1+12 byte ifg and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 76.19, frame_size=6+6+2+46+4, interframe_gap=7+1+12)
	step=step+1

	#3 - Generate 50% traffic load with maximum frame size 6+6+2+1500+4 byte packets 7+1+12+1498 byte ifg and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 50, frame_size=6+6+2+1500+4, interframe_gap=7+1+12+1498, frames_per_burst=0, interburst_gap=0)
	step=step+1

	#4 - Generate 50% traffic load with minimum frame size 6+6+2+46+4 byte packets 7+1+12+44 byte ifg and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 50, frame_size=6+6+2+46+4, interframe_gap=7+1+12+44)
	step=step+1

	#5 - Generate 5% traffic load with maximum frame size 6+6+2+1500+4 byte packets 7+1+12+28822 byte ifg and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 5,  frame_size=6+6+2+1500+4, interframe_gap=7+1+12+28822)
	step=step+1

	#6 - Generate 50% burst traffic load 6+6+2+1500+4 byte packets 7+1+12 byte ifg, frames-per-burst=10, interburst-gap=7+1+12+14980 and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 50, frame_size=6+6+2+1500+4, interframe_gap=7+1+12, frames_per_burst=10, interburst_gap=7+1+14980)
	step=step+1

	#7 - Generate 5% burst traffic load 6+6+2+1500+4 byte packets 7+1+12 byte ifg, frames-per-burst=10, interburst-gap=7+1+12+288220 and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 5,  frame_size=6+6+2+1500+4, interframe_gap=7+1+12, frames_per_burst=10, interburst_gap=7+1+288220)
	step=step+1

	#8 - Generate 10% burst traffic load 6+6+2+1500+4 byte packets 7+1+12+27284 byte ifg, frames-per-burst=2, interburst-gap=7+1+12 and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 10,  frame_size=6+6+2+1500+4, interframe_gap=7+1+12+27284, frames_per_burst=2, interburst_gap=7+1+12)
	step=step+1

	#9 - Generate maximum traffic load with minimum frame size 76.19% traffic load 6+6+2+46+4 byte packets 7+1+12 byte ifg, frames-per-burst=2, interburst-gap=7+1+12 and verify counters.
	(bw_expected[step],bw_generated[step]) = validate(network, conns, yconns, mylinks, 76.19,  frame_size=6+6+2+46+4, interframe_gap=7+1+12, frames_per_burst=2, interburst_gap=7+1+12)
	step=step+1

	display_table(bw_expected,bw_generated)
	return 0

sys.exit(main())
