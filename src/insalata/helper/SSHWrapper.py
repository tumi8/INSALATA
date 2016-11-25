import paramiko
import json
from lxml import etree
import time

class SSHClient_noAuth(paramiko.SSHClient):
    def _auth(self, username, *args):
        self._transport.auth_none(username)
        return

class SSHWrapper:
    def __init__(self):
        self.user = "root"
        self.name = None
        self.key = paramiko.rsakey.RSAKey(filename="/etc/ssh/ssh_host_rsa_key")
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
    def connect(self, name):
        self.name = name
        self.ssh.connect(name, username=self.user, pkey=self.key)
        
    def close(self):
        self.ssh.close()

    def getConnection(self):
        return self.ssh

    ############################################################################
    # Methods for gathering information from existing hosts
    ############################################################################
    def executeTcpdump(self, args):
        _, stdout, _ = self.ssh.exec_command("tcpdump {}".format(args))
        return stdout

    def getInterfaceInfo(self):
        with open('/etc/insalata/template/hostScripts/read_InterfaceInformation') as f:
            script =f.read().replace("$", "\$")
            self.ssh.exec_command('cat > ./read_InterfaceInformation <<DEL\n' + script + '\nDEL')
            self.ssh.exec_command('chmod +x ./read_InterfaceInformation')
        ifaces = list()
        _, stdout, _ = self.ssh.exec_command('bash ./read_InterfaceInformation')
        for iface in stdout.readlines():
            ifaces.append(json.loads(iface))
        return ifaces

    def getDNSInfo(self):
        with open('/etc/insalata/template/hostScripts/read_DNSServer') as f:
            script =f.read().replace("$", "\$")
            self.ssh.exec_command('cat > ./read_DNSServer <<DEL\n' + script + '\nDEL')
            self.ssh.exec_command('chmod +x ./read_DNSServer')
        _, stdout, _ = self.ssh.exec_command('bash ./read_DNSServer')
        stdout.channel.recv_exit_status() # Synchronize
        output = ""
        for line in stdout:
            output += line
        return json.loads(output) if output != "" else None

    def getDHCPInfo(self):
        with open('/etc/insalata/template/hostScripts/read_DHCPServer') as f:
            script =f.read().replace("$", "\$")
            self.ssh.exec_command('cat > ./read_DHCPServer <<DEL\n' + script + '\nDEL')
            self.ssh.exec_command('chmod +x ./read_DHCPServer')
        _, stdout, _ = self.ssh.exec_command('bash ./read_DHCPServer')
        stdout.channel.recv_exit_status() # Synchronize
        output = ""
        for line in stdout:
            output += line
        return json.loads(output) if output != "" else None

    def getRoutingInfo(self):
        with open('/etc/insalata/template/hostScripts/read_Routing') as f:
            script = f.read().replace("$", "\$")
            self.ssh.exec_command('cat > ./read_Routing <<DEL\n' + script + '\nDEL')
            self.ssh.exec_command('chmod +x ./read_Routing')
        _, stdout, _ = self.ssh.exec_command('bash ./read_Routing')
        stdout.channel.recv_exit_status() # Synchronize
        output = ""
        for line in stdout:
            output += line
        return json.loads(output) if output != "" else None

    def executeNmapServiceScan(self, serviceOptions, range):
        #Do a ping scan to detect living hosts -> Store them in host file
        _, stdout, _ = self.ssh.exec_command("nmap -sn --max-retries=1 --max-parallelism=256 --min-parallelism=100 -T4 -n " + range + " | grep report | awk '{print $5}' > hosts")
        stdout.channel.recv_exit_status()
        
        #Do the service detection
        _, stdout, _ = self.ssh.exec_command("nmap -iL hosts -oX scan.xml -sV " + serviceOptions)
        stdout.channel.recv_exit_status()


        _, stdout, _ = self.ssh.exec_command("cat scan.xml")
        output = ""
        for line in stdout:
            output += line
        #self.ssh.exec_command("rm scan.xml")
        #self.ssh.exec_command("rm hosts")
        return etree.fromstring(output)