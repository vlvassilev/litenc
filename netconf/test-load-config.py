from netconf import netconf_connect, netconf_load_config, netconf_terminate, netconf_xget_leaf_value

serverip="192.168.209.31"
gatewayip="192.168.209.1"
port=830
user="root"
password="hadm1_123"

print "Connect to server:"
my_netconf = netconf_connect(serverip, port, user, password)
if my_netconf == None:
    print "FAILED"
    exit(-1)
else:
    print "OK"

config = '<config>\
   <routes xmlns="http://transpacket.com/ns/routes">\
     <route>\
       <destination-prefix>0.0.0.0/0</destination-prefix>\
       <next-hop>%(gatewayip)s</next-hop>\
     </route>\
   </routes>\
   <interfaces xmlns="http://transpacket.com/ns/hadm1-interfaces">\
     <interface>\
       <name>me0</name>\
       <inet>\
         <address>%(serverip)s/24</address>\
       </inet>\
     </interface>\
     <interface>\
       <name>ge0</name>\
     </interface>\
   </interfaces>\
 </config>' % {'serverip':serverip, 'gatewayip':gatewayip}

print "Load configuration:"
ret = netconf_load_config(my_netconf, config)
if ret==0:
    print "OK"
else:
    print "FAILED"

print "Get status:"
(ret, value) = netconf_xget_leaf_value(my_netconf, '/interfaces/interface[name=\'me0\']/link-state')
if ret==0:
    print 'OK,value=%s' % value
else:
    print "FAILED"

netconf_terminate(my_netconf)

