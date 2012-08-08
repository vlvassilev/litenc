import paramiko
import socket

class netconf:
    def __init__(self):
        self.t = None
        self.chan = None
        self.sock = None

    def connect(self, arg):
        #arg="server=192.168.209.31 port=830 user=root password=hadm1_123"
        print "connecting: " + arg
        args = arg.split(" ");
        user="root"
        password="hadm1_123"
        server="192.168.209.31"
        port=830

        for i in range(0,len(args)):
            current_pair = args[i].split("=")
            if current_pair[0] == "user":
                user=current_pair[1]
                print "user is " + user
            if current_pair[0] == "password":
                password=current_pair[1]
                print "password is " + password
            if current_pair[0] == "server":
                server=current_pair[1]
                print "server is " + server
            if current_pair[0] == "port":
                port=int(current_pair[1])
                print "port is " + str(port)

        # now connect
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((server, port))
        except Exception, e:
            print '*** Connect failed: ' + str(e)
            traceback.print_exc()
            return -1

        try:
            self.t = paramiko.Transport(self.sock)
            try:
                self.t.start_client()
            except paramiko.SSHException:
                print '*** SSH negotiation failed.'
                return -1
        except Exception, e:
            print '*** Connect failed: ' + str(e)
            traceback.print_exc()
            return -1


        # TODO: check server's host key -- this is important.
        key = self.t.get_remote_server_key()
        print key

        self.t.auth_password(user, password)

        if not self.t.is_authenticated():
            print '*** Authentication failed. :('
            self.t.close()
            return -1

        self.chan = self.t.open_session()

        self.chan.set_name("netconf")
        self.chan.invoke_subsystem("netconf")
        return 0

    def rpc(self, xml):
        print "sending: " + xml
        try:
            data = xml + "]]>]]>"
            while data:
                n = self.chan.send(data)
                print "sent " + str(n)
                if n <= 0:
                    return -1
                data = data[n:]
        except Exception, e:
            print '*** Caught exception: ' + str(e.__class__) + ': ' + str(e)
            traceback.print_exc()
            return -1

        #receive reply
        print "receiving ..."
        total_data = ""
        while True:
            data = self.chan.recv(4096)
            if data:
                print "got: " + str(data)
                total_data = total_data + str(data)
            else:
                return -1

            xml_len = total_data.find("]]>]]>")
            if xml_len >= 0:
                reply_xml = total_data[:xml_len]
                break

        return (0,reply_xml)

    def terminate(self):
        print "terminating"
        self.chan.close()
        self.t.close()

        return
