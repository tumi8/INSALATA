from insalata.model.Host import Host
from insalata.model.Layer3Network import Layer3Network
from insalata.scanner.modules import base
from insalata.model.Layer3Address import Layer3Address
import json
import itertools
import subprocess
from lxml import etree


def scan(graph, connectionInfo, logger, thread):
    """
    Get all services using a nmap scan.
    Scanning is executed on the host given in the configuration.
    Therefore, Nmap must be installed on the scanning device.

    Necessary values in the configuration file of this collector module:
        - timeout           Timeout this collector module shall use (Integer)
        - hosts             List of network components we shall use to run Nmap. The collector
                            connects to the network components in the list using ssh and runs athe Nmap scan.
                            We will not use ssh for 'localhost'.
                            The used config parser generates a list if the elements are separated by a comma: localhost, myServer as an example
        - control_networks  (Optional) Json-Array of Layer three Networks we do NOT want to scan using Nmap
        - options           (Optional) Additional Options we want to use for the Nmap scan
    
    :param graph: Data interface object for this collector module
    :type graph: insalata.model.Graph.Graph

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: logging:Logger

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """

    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    logger.info("Executing nmap service scan.")
    if(type(connectionInfo['hosts']) != list):
        connectionInfo['hosts'] = [connectionInfo['hosts']]
    for hostName in connectionInfo['hosts']:
        logger.debug("Executing Nmap on network component: '{}'".format(hostName))
        if hostName != "localhost":
            scanHost = [h for h in graph.getAllNeighbors(Host) if h.getID() == hostName] #Host executing nmap
            if len(scanHost) == 0: # Error handling if nmap host not in graph
                logger.error("No host object found for hostname {0}. Nmap scan failed!".format(hostName))
                continue
            host = scanHost[0]

            if not ((host.getPowerState() is None) or (host.getPowerState() == 'Running')):
                logger.error("Host {0} is not running. Skipping nmap scan")
                continue
            ssh = base.getSSHConnection(host)
            logger.debug("Execute nmap service scan on host {0}.".format(hostName))
            if ssh is None: #No ssh connecton is possible -> Skip this host
                logger.info("Skipping host {0} as ssh connection failed.".format(host.getID()))
                continue

        for networkNode in graph.getAllNeighbors(Layer3Network):
            net = networkNode.getAddress() + "/" + str(networkNode.getPrefix())
            if "control_networks" in connectionInfo and net in json.loads(connectionInfo["control_networks"]): #Skip this one
                logger.debug("Skipping nmap on host {0} for network: {1}.".format(hostName, net))
                continue
            logger.debug("Executing nmap with additional options '{0}' on host {1} for network: {2}.".format(connectionInfo["options"], hostName, net))
            try: # Error handling e.g. if no nmap executable on host
                options = connectionInfo['options'] if "options" in connectionInfo else ""
                if hostName != "localhost":
                    scanXml = ssh.executeNmapServiceScan(options, net)
                else:
                    proc = subprocess.Popen("nmap -iL hosts -oX - -sV {}".format(options).split(" "), stdout=subprocess.PIPE)
                    stdout = proc.stdout

                    res = stdout.channel.recv_exit_status() # Error handling e.g. if no nmap executable on localhost
                    if res != 0:
                        raise OSError(res, "Nmap service scan on localhost failed. Result: {}".format(res))
                    output = ""
                    for line in stdout:
                        output += line

                    subprocess.Popen("rm hosts")
                    output = output.replace('encoding="UTF-8"','') # Avoid encoding problems in ElementTree
                    scanXml = etree.fromstring(output)
            except OSError as e:
                logger.error("Exit status {1} during nmap scan on host {0}: {2}. Is Nmap installed on the scanning device?".format(host.getID(), e.errno, e.strerror))
                continue

            for hostXml in scanXml.findall("host"):
                for addrXml in hostXml.findall("address"):
                    if addrXml.attrib["addrtype"] == "mac":
                        continue
                    address = addrXml.attrib["addr"]
                    logger.debug("Found entry for address {0} in nmap scan.".format(address))
                    addressNode = getAddressNode(networkNode, address)
                    if addressNode is None:
                        addressNode = graph.getOrCreateLayer3Address(address, name, timeout)

                    portsXml = hostXml.find("ports")
                    for portXml in portsXml.findall("port"):
                        protocol = portXml.attrib["protocol"]
                        port = int(portXml.attrib["portid"])

                        serviceXml = portXml.find("service")
                        if serviceXml is not None:
                            if "name" in serviceXml.attrib and serviceXml.attrib["name"] != "unknown":
                                serviceName = serviceXml.attrib["name"]
                                logger.debug("Add service '{0}' to address {1}".format(serviceName, address))

                                serviceNode = None
                                if serviceName == "domain": #DNS
                                    serviceNode = graph.getOrCreateDnsService(name, timeout, addressNode)
                                if serviceName == "dhcps":
                                    serviceNode = graph.getOrCreateDhcpService(name, timeout, addressNode)
                                else:
                                    serviceNode = graph.getOrCreateService(port, protocol, name, timeout, serviceName ,addressNode)

                                if "product" in serviceXml:
                                    serviceNode.setProduct(serviceXml.attrib["product"]), name, timeout
                                if "version" in serviceXml:
                                    serviceNode.setVersion(serviceXml["version"], name, timeout)

                                serviceNode.verify(name, timeout)
                                addressNode.addService(serviceNode)

                    addressNode.verify(name, timeout)

                for host in [h for h in graph.getAllNeighbors(Host) if h.getID() == hostName.split(".")[0]]:
                    host.verify(name, timeout)
        base.releaseSSHConnection(ssh)


def getAddressNode(network, address):
    """
    Get the Layer3Address node of a host that has the igven address.
    
    :param network: Hostnames the host could have -> Nmap scan
    :type network: Layer3Network

    :param address: Address to find
    :type address: str

    :returns: Layer3Address node or None
    :rtype: Layer3Address
    """

    addresses = [a for a in network.getAllNeighbors(Layer3Address) if a.getID() == address]
    if len(addresses) == 0:
        return None
    return addresses[0]