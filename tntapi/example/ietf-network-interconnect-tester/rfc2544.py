#!/usr/bin/python3

from lxml import etree
import time
import math
import sys, os
import subprocess
import argparse
import tntapi
import yangrpc
from MLRsearch import Config, MeasurementResult, MultipleLossRatioSearch, SearchGoal
from yangcli.yangcli import yangcli

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network",
	"nt":"urn:ietf:params:xml:ns:yang:ietf-network-topology",
	"if":"urn:ietf:params:xml:ns:yang:ietf-interfaces",
	"tg":"urn:ietf:params:xml:ns:yang:ietf-traffic-generator",
	"ta":"urn:ietf:params:xml:ns:yang:ietf-traffic-analyzer"
}

args=None
network=None
conns=None
yconns=None
frame_data=None

def get_delta_counter(before,after,node_name,inst_id_xpath):
	return int(after.xpath("node[node-id='"+node_name+"']/data/"+inst_id_xpath)[0].text) - int(before.xpath("node[node-id='"+node_name+"']/data/"+inst_id_xpath)[0].text)

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


	rx_in_pkts=1.0*int(after.xpath("""node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/pkts"""%(dst_node, dst_node_interface))[0].text)

	latency_nodes = after.xpath("""node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency"""%(dst_node, dst_node_interface))
	if(len(latency_nodes) == 1):
		latency_min = int(after.xpath("node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency/min"%(dst_node, dst_node_interface))[0].text)
		latency_max = int(after.xpath("node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency/max"%(dst_node, dst_node_interface))[0].text)
		#latency_average = int(after.xpath("node[node-id='%s']/data/interfaces/interface[name='%s']/traffic-analyzer/state/testframe-stats/latency/average"%(dst_node, dst_node_interface))[0].text)
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
	speed = int(state_before_wo_ns.xpath("node[node-id='%s']/data/interfaces-state/interface[name='%s']/speed"%(src_node, src_node_interface))[0].text)

	if(frames_per_burst == 0):
		total_frames = int(math.floor(test_time*speed/((interframe_gap+frame_size)*8)))
	else:
		total_frames = int(math.floor(frames_per_burst*test_time*speed/(((frames_per_burst-1)*interframe_gap+frames_per_burst*frame_size+interburst_gap)*8)))

	testframe = ""
	if(testframe_type != []):
		testframe = "testframe-type=%s" % testframe_type
	print("""create /interfaces/interface[name="%(name)s"]/traffic-generator -- frame-size=%(frame-size)d interframe-gap=%(interframe-gap)d total-frames=%(total-frames)s %(burst)s frame-data=%(frame-data)s %(testframe)s""" % {'name':src_node_interface,'frame-size':frame_size, 'interframe-gap':interframe_gap, 'burst':my_burst_config, 'total-frames':total_frames, 'frame-data':frame_data, 'testframe':testframe})
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
	time.sleep(2)

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

class TrialMeasurer:
	def __init__(self, pps_top, speed, network, conns, yconns, frame_size, src_node, src_node_interface, dst_node, dst_node_interface, src_mac_address, dst_mac_address, frame_data, testframe_type):
		self.pps_top, self.speed, self.network, self.conns, self.yconns, self.frame_size, self.src_node, self.src_node_interface, self.dst_node, self.dst_node_interface, self.src_mac_address, self.dst_mac_address, self.frame_data, self.testframe_type = pps_top, speed, network, conns, yconns, frame_size, src_node, src_node_interface, dst_node, dst_node_interface, src_mac_address, dst_mac_address, frame_data, testframe_type
		self.i = 0
	def measure(intended_duration, intended_load):
		self.i += 1
		interframe_gap = ((speed/8) - frame_size*(intended_load))/(intended_load)
		interframe_gap = math.ceil(interframe_gap)
		print ("%d %f pps, %d octets interframe gap ... "%(self.i, intended_load, interframe_gap))
		(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average) = trial(self.network, self.conns, self.yconns, test_time=intended_duration, frame_size=self.frame_size, interframe_gap=interframe_gap, interburst_gap=0, frames_per_burst=0, src_node=self.src_node, src_node_interface=self.src_node_interface, dst_node=self.dst_node, dst_node_interface=self.dst_node_interface, src_mac_address=self.src_mac_address, dst_mac_address=self.dst_mac_address, frame_data=self.frame_data, testframe_type=self.testframe_type)
		print ("#%d %f pps, %d octets interframe gap, %02.2f%% ... %d / %d"%(self.i, intended_load, interframe_gap, 100.0*intended_load/self.pps_top, rx_testframe_pkts, generated_pkts))
		return MeasurementResult(intended_duration, intended_load, generated_pkts, None, rx_testframe_pkts)

def test_throughput():

	global args
	global network
	global conns
	global yconns
	global frame_data

	speed = int(args.speed)
	frame_size = int(args.frame_size)
	interframe_gap_min = int(args.interframe_gap_min)
	pps_top = (float)(speed/8)/(interframe_gap_min+frame_size)
	pps_bottom = 2.0

	measurer = TrialMeasurer(pps_top, speed, network, conns, yconns, frame_size=frame_size, src_node=args.src_node, src_node_interface=args.src_node_interface, dst_node=args.dst_node, dst_node_interface=args.dst_node_interface, src_mac_address=args.src_mac_address, dst_mac_address=args.dst_mac_address, frame_data=frame_data, testframe_type=args.testframe_type)
	goal = SearchGoal(loss_ratio=0.0, exceed_ratio=0.0, final_trial_duration=int(args.trial_time), duration_sum=int(args.trial_time))
	config = Config(goals=[goal], min_load=pps_bottom, max_load=pps_top, warmup_duration=None)
	result = MultipleLossRatioSearch(config=config).search(measurer=measurer)
	throughput = result[goal].conditional_throughput

	# TODO: Should the following be for last trial of sum across all trials?
	#print("Test time:                      %8u"%(int(args.trial_time)))
	#print("Generated packets:              %8u"%(generated_pkts))
	#print("Received  packets:              %8u"%(rx_testframe_pkts))
	##print("Generated octets MB/s:          %8f"%(generated_pkts*float(args.frame_size)/(int(args.trial_time)*1024*1024))
	#print("Lost packets:                   %8u"%(generated_pkts-rx_testframe_pkts))
	#print("Lost packets percent:           %2.6f"%(100*float(generated_pkts-rx_testframe_pkts)/generated_pkts))

	# TODO: Subclass MeasurementResult so the following can be returned:
	#if(sequence_errors != None):
	#	print("Sequence errors:                %8u"%(sequence_errors))
	#	print("Sequence errors percent:        %2.6f"%(100*float(sequence_errors)/generated_pkts))
	#if(latency_min != None and rx_testframe_pkts>0):
	#	print("Latency Min[nanoseconds]:       %8u"%(latency_min))
	#	print("Latency Max[nanoseconds]:       %8u"%(latency_max))
	#else:
	#	print("Latency Min[nanoseconds]:       NA")
	#	print("Latency Max[nanoseconds]:       NA")

	print("#Result: %f pps"%(throughput))
	return throughput

def test_latency(throughput_pps_max):
	global args
	global network
	global conns
	global yconns
	global frame_data

	print("#Measurement style - bit forwarding")
	speed = int(args.speed)
	frame_size = int(args.frame_size)

	interframe_gap = (speed/8 - frame_size*(throughput_pps_max))/(throughput_pps_max)
	interframe_gap = math.ceil(interframe_gap)
	latency_sum = 0
	i=1
	while(i<=20):
		print ("%d, %f pps, %d octets interframe gap ... "%(i, throughput_pps_max, interframe_gap))
		(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average) = trial(network, conns, yconns, test_time=int(args.trial_time), frame_size=frame_size, interframe_gap=interframe_gap, interburst_gap=0, frames_per_burst=0, src_node=args.src_node, src_node_interface=args.src_node_interface, dst_node=args.dst_node, dst_node_interface=args.dst_node_interface, src_mac_address=args.src_mac_address, dst_mac_address=args.dst_mac_address, frame_data=frame_data, testframe_type=args.testframe_type)
		if(rx_testframe_pkts == generated_pkts):
			ok = True
		else:
			ok = False

		print ("#%d %d ns (min=%d ns, max=%d ns) ... %d / %d"%(i, latency_max, latency_min, latency_max, rx_testframe_pkts, generated_pkts))
		latency_sum = latency_sum + latency_max
		i=i+1

	latency = 1.0*latency_sum/20
	print("#Result: %f nanoseconds"%(latency))

	return latency

def test_frame_loss_rate():
	global args
	global network
	global conns
	global yconns
	global frame_data

	speed = int(args.speed)
	frame_size = int(args.frame_size)
	interframe_gap_min = int(args.interframe_gap_min)

	pps_top = (float)(speed/8)/(interframe_gap_min+frame_size)
	ok = False
	for i in range(0,10):
		ratio=1-0.1*i
		pps = pps_top*ratio
		interframe_gap = ((speed/8) - frame_size*(pps))/(pps)
		interframe_gap = math.ceil(interframe_gap)

		actual_pps = (float)(speed/8) / (frame_size+interframe_gap)
		print ("%d %f pps, %d octets interframe gap ... "%(i, pps, interframe_gap))
		(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average) = trial(network, conns, yconns, test_time=int(args.trial_time), frame_size=frame_size, interframe_gap=interframe_gap, interburst_gap=0, frames_per_burst=0, src_node=args.src_node, src_node_interface=args.src_node_interface, dst_node=args.dst_node, dst_node_interface=args.dst_node_interface, src_mac_address=args.src_mac_address, dst_mac_address=args.dst_mac_address, frame_data=frame_data, testframe_type=args.testframe_type)

		print ("#%d %d%% rate, %d%% loss, (%f%% rate actual), %f pps (%f pps actual), %d octets interframe gap ... %d / %d"%(i+1, ratio*100, 100*(generated_pkts-rx_testframe_pkts)/generated_pkts, ratio*100*actual_pps/pps, pps, actual_pps, interframe_gap, rx_testframe_pkts, generated_pkts))
		if(rx_testframe_pkts == generated_pkts):
			
			if(ok):
				#two successive trials in which no frames are lost
				break
			ok = True
		else:
			ok = False

	return 

def test_back_to_back_frames():
	global args
	global network
	global conns
	global yconns
	global frame_data


	speed = int(args.speed)
	frame_size = int(args.frame_size)
	interframe_gap = int(args.interframe_gap_min)

	pps_top = (float)(speed/8)/(interframe_gap+frame_size)
	frames_per_burst = 2
	frames_per_burst_low = 1
	frames_per_burst_high = 0
	i=1
	while(i<32):

		interburst_gap = math.ceil(2*speed/8 - frames_per_burst*(interframe_gap+frame_size))
		print ("%d %f back-to-back frames ... "%(i, frames_per_burst))
		(rx_in_pkts, rx_testframe_pkts, generated_pkts, sequence_errors, latency_min, latency_max, latency_average) = trial(network, conns, yconns, test_time=int(args.trial_time), frame_size=int(args.frame_size), interframe_gap=interframe_gap, interburst_gap=interburst_gap, frames_per_burst=frames_per_burst, src_node=args.src_node, src_node_interface=args.src_node_interface, dst_node=args.dst_node, dst_node_interface=args.dst_node_interface, src_mac_address=args.src_mac_address, dst_mac_address=args.dst_mac_address, frame_data=frame_data, testframe_type=args.testframe_type)
		if(rx_testframe_pkts == generated_pkts):
			ok = True
		else:
			ok = False

		print ("#%d %d back-to-back frames ... %d / %d"%(i, int(frames_per_burst), rx_testframe_pkts, generated_pkts))

		if(ok):
			frames_per_burst_low = frames_per_burst
			if(frames_per_burst_high==0):
				frames_per_burst = frames_per_burst*2
			else:
				frames_per_burst = math.ceil(frames_per_burst_low+(frames_per_burst_high-frames_per_burst_low)/2)
		else:
			frames_per_burst_high = frames_per_burst
			frames_per_burst = math.floor(frames_per_burst_high-(frames_per_burst_high-frames_per_burst_low)/2)

		#Limit the tested range to 1 second continuous burst
		if(frames_per_burst>pps_top):
			frames_per_burst_high = math.floor(pps_top)
			frames_per_burst = frames_per_burst_high

		if(frames_per_burst_low!=0 and frames_per_burst_high!=0 and (frames_per_burst_high-frames_per_burst_low)<=1):
			break
		i = i + 1
	if(frames_per_burst == frames_per_burst_high):
		print("#The back to back search is limited to bursts below 1 second.")
		print("#Result: >= %d"%(frames_per_burst_low))
	else:
		print("#Result: %d"%(frames_per_burst_low))

def test_system_recovery():
	print("#TODO")

def test_reset():
	print("#TODO")

def main():
	pass

if __name__ == "__main__":

	parser = argparse.ArgumentParser()
	parser.add_argument("--config", help="Path to the netconf configuration *.xml file defining the configuration according to ietf-networks, ietf-networks-topology and netconf-node models e.g. ../networks.xml")
	parser.add_argument('--frame-size', default="64",help="Frame size.")
	parser.add_argument('--interframe-gap-min', default="20",help="Minimum interframe gap (including preamble) e.g. 20 = 12 minimum gap + 8 preamble for Ethernet.")
	parser.add_argument('--src-node', default=[],help="Transmitting node.")
	parser.add_argument('--src-node-interface', default=[],help="Transmitting node port.")
	parser.add_argument('--dst-node', default=[],help="Receiving node.")
	parser.add_argument('--dst-node-interface', default=[],help="Receiving node port.")
	parser.add_argument('--src-mac-address', default="01:23:45:67:89:AB",help="Source MAC address.")
	parser.add_argument('--dst-mac-address', default="01:23:45:67:89:AC",help="Destination MAC address.")
	parser.add_argument('--src-ipv4-address', default="192.168.0.1",help="Source ipv4 address.")
	parser.add_argument('--dst-ipv4-address', default="192.168.0.2",help="Destination ipv4 address.")
	parser.add_argument('--src-ipv4-udp-port', default="",help="Source ipv4 UDP port.")
	parser.add_argument('--dst-ipv4-udp-port', default="7",help="Destination ipv4 UDP port.")
	parser.add_argument('--ipv4-ttl', default="10",help="ipv4 TTL field.")
	parser.add_argument('--speed', default="1000000000",help="Maximum interface speed in bits per second e.g 1000000000 for 1Gb Ethernet interface.")
	parser.add_argument('--trial-time', default="2",help="Time each trial takes in seconds.")
	parser.add_argument('--testframe-type', default="dynamic",help="Type of generated testframe e.g. static or dynamic")

	args = parser.parse_args()

	tree=etree.parse(args.config)
	network = tree.xpath('/nc:config/nd:networks/nd:network', namespaces=namespaces)[0]

	conns = tntapi.network_connect(network)
	yconns = tntapi.network_connect_yangrpc(network)
	mylinks = tntapi.parse_network_links(network)

	assert(conns != None)
	assert(yconns != None)

	frame_data = subprocess.check_output(("traffic-generator-make-testframe --frame-size=%(frame_size)s --dst-mac-address=%(dst_mac_address)s --src-mac-address=%(src_mac_address)s --src-ipv4-address=%(src_ipv4_address)s --ipv4-ttl=%(ipv4_ttl)s --src-ipv4-udp-port=49184 --dst-ipv4-address=%(dst_ipv4_address)s --dst-ipv4-udp-port=%(dst_ipv4_udp_port)s"%{'frame_size':args.frame_size, 'dst_mac_address':args.dst_mac_address, 'src_mac_address':args.src_mac_address, 'src_ipv4_address':args.src_ipv4_address, 'ipv4_ttl':args.ipv4_ttl, 'dst_ipv4_address':args.dst_ipv4_address, 'dst_ipv4_udp_port':args.dst_ipv4_udp_port}).split(' ')).decode('utf-8').rstrip()

	print("#===Throughput===")
	throughput_pps = test_throughput()
	print("#===Latency===")
	test_latency(throughput_pps)
	print("#===Frame loss rate===")
	test_frame_loss_rate()
	print("#===Back to back frames===")
	test_back_to_back_frames()
	print("#===System recovery===")
	test_system_recovery()
	print("#===Reset===")
	test_reset()

	sys.exit(0)
