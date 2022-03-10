#!/usr/bin/python

# Usage:
# $> ./report-cameras.py before.xml after.xml > cameras.html


import lxml
from lxml import etree
import time
import sys, os
import argparse
from datetime import datetime
import tntapi
import base64

namespaces={"nc":"urn:ietf:params:xml:ns:netconf:base:1.0",
	"nd":"urn:ietf:params:xml:ns:yang:ietf-network"}
def main():

	before_config=etree.parse(sys.argv[1])
	before_networks = before_config.xpath('/nc:config/nd:networks',namespaces=namespaces)[0]
	before_network = before_networks.xpath('nd:network',namespaces=namespaces)[0]

	after_config=etree.parse(sys.argv[2])
	after_networks = after_config.xpath('/nc:config/nd:networks',namespaces=namespaces)[0]
	after_network = after_networks.xpath('nd:network',namespaces=namespaces)[0]

	before=tntapi.strip_namespaces(before_network)
	after=tntapi.strip_namespaces(after_network)


	print("<html><head></head><body>")
	nodes = after.xpath('node')
	for node in nodes:
		node_id = node.xpath('node-id')[0].text
		cameras=node.xpath("data/cameras/camera")
		for camera in cameras:
			camera_name = camera.xpath('name')[0].text
			image_before = before.xpath("node[node-id='%s']/data/cameras/camera[name='%s']/image"%(node_id, camera_name))
			image_after = after.xpath("node[node-id='%s']/data/cameras/camera[name='%s']/image"%(node_id, camera_name))
			file_before = open('%s-%s-before.jpg'%(node_id,camera_name), "w")
			n = file_before.write(base64.b64decode(image_before[0].text))
			file_before.close()
			file_after = open('%s-%s-after.jpg'%(node_id,camera_name), "w")
			n = file_after.write(base64.b64decode(image_after[0].text))
			file_after.close()

			print('''<a target="_blank" href="%s-%s-before.jpg"><img src="%s-%s-before.jpg" alt="before" width="450"></a>'''%(node_id,camera_name,node_id,camera_name))
			print('''<a target="_blank" href="%s-%s-after.jpg"><img src="%s-%s-after.jpg" alt="after" width="450"></a>'''%(node_id,camera_name,node_id,camera_name))
	print('''</body></html>''')


	return 0

sys.exit(main())
