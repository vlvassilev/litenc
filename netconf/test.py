import netconf

my_netconf = netconf.netconf()
my_netconf.connect("server=192.168.209.31 port=830 user=root password=hadm1_123")
(ret, reply_xml) = my_netconf.rpc("<hello>\
 <capabilities>\
   <capability>urn:ietf:params:netconf:base:1.0</capability>\
 </capabilities>\
</hello>")
print reply_xml

(ret, reply_xml) = my_netconf.rpc('<rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\
 <get>\
   <filter type="xpath" select="/"/>\
 </get>\
</rpc>')
print reply_xml

my_netconf.terminate()

