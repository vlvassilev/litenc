#helper API
import netconf
from xml.dom.minidom import parseString

def netconf_connect(serverip, port, user, password):
    my_netconf = netconf.netconf()
    ret = my_netconf.connect('server=%(serverip)s port=%(port)d user=%(user)s password=%(password)s' % {'serverip':serverip, 'port':port, 'user':user, 'password':password})
    if ret != 0:
        return None

    ret = my_netconf.send("<hello>\
     <capabilities>\
       <capability>urn:ietf:params:netconf:base:1.0</capability>\
     </capabilities>\
    </hello>")
    if ret != 0:
        return None
    (ret, reply_xml)=my_netconf.receive()
    if ret != 0:
        return None
    return my_netconf

def netconf_load_config(my_netconf, config):
    edit_config_rpc='<rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\
<edit-config>\
 <target>\
   <candidate/>\
 </target>\
 <default-operation>replace</default-operation>\
%s\
</edit-config>\
</rpc>' % config

    (ret, reply_xml) = my_netconf.rpc(edit_config_rpc)
    if ret != 0:
        return (ret, reply_xml)
    reply_dom = parseString(reply_xml)
    assert reply_dom.documentElement.tagName == "rpc-reply"
    iserror = reply_dom.getElementsByTagName("rpc-error")
    if len(iserror) != 0:
        print config
        print reply_xml
        return (ret, reply_xml)
    
    (ret, reply_xml) = my_netconf.rpc('<rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\
    <commit/>\
    </rpc>')
    if ret != 0:
        print config
        print reply_xml
        return (ret, reply_xml)
    reply_dom = parseString(reply_xml)
    assert reply_dom.documentElement.tagName == "rpc-reply"
    iserror = reply_dom.getElementsByTagName("rpc-error")
    if len(iserror) != 0:
        return (len(iserror), reply_xml)

    return 0

def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

def netconf_xget_leaf_value(my_netconf, xpath):
    get_rpc='<rpc message-id="101"\
  xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\
  <get>\
    <filter type="xpath" select=\"%s\"/>\
  </get>\
 </rpc>' % xpath
    (ret, reply_xml) = my_netconf.rpc(get_rpc)
    if ret != 0:
        return -1
    reply_dom = parseString(reply_xml)
    assert reply_dom.documentElement.tagName == "rpc-reply"
    isdata = reply_dom.getElementsByTagName("data")
    if isdata == None  or len(isdata) == 0:
        return -1
    xpath_split = xpath.split("/")
    value_name = xpath_split[-1]
    value_dom = reply_dom.getElementsByTagName(value_name)[0]

    return (0,getText(value_dom.childNodes))

def netconf_xget_config_container_value(my_netconf, xpath):
    get_rpc='<rpc message-id="101"\
  xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\
  <get-config>\
    <source>\
      <running/>\
    </source>\
    <filter type="xpath" select=\"%s\"/>\
  </get-config>\
 </rpc>' % xpath
    (ret, reply_xml) = my_netconf.rpc(get_rpc)
    if ret != 0:
        return -1
    reply_dom = parseString(reply_xml)
    assert reply_dom.documentElement.tagName == "rpc-reply"
    isdata = reply_dom.getElementsByTagName("data")
    if isdata == None or len(isdata) == 0:
        return -1

    isdata[0].tagName = "config"
    return (0,isdata[0].toxml())

def netconf_xget_container_value(my_netconf, xpath):
    get_rpc='<rpc message-id="101"\
  xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\
  <get>\
    <filter type="xpath" select=\"%s\"/>\
  </get>\
 </rpc>' % xpath
    (ret, reply_xml) = my_netconf.rpc(get_rpc)
    if ret != 0:
        return -1
    reply_dom = parseString(reply_xml)
    assert reply_dom.documentElement.tagName == "rpc-reply"
    isdata = reply_dom.getElementsByTagName("data")
    if isdata == None or len(isdata) == 0:
        return -1
    isdata[0].tagName = "status"
    return (0,isdata[0].toxml())


def netconf_terminate(my_netconf):
    my_netconf.terminate()


