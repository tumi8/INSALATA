from insalata.model.Host import Host
from insalata.model.Layer3Network import Layer3Network
from insalata.scanner.modules import base
from insalata.model.Layer3Address import Layer3Address
import json
import itertools


def scan(graph, connectionInfo, logger, thread):
    """
    Get all services using a nmap scan.
    Scanning is executed on the host given in the configuration.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """

    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    logger.info("Executing nmap service scan.")
    for hostName in json.loads(connectionInfo['hosts']):
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
            if "control_networks" in connectionInfo and net in connectionInfo["control_networks"]: #Skip this one
                logger.debug("Skipping nmap on host {0} for network: {1}.".format(hostName, net))
                continue
            logger.debug("Executing nmap with additional options '{0}' on host {1} for network: {2}.".format(connectionInfo["options"], hostName, net))
            try: # Error handling e.g. if no nmap executable on host
                scanXml = ssh.executeNmapServiceScan(connectionInfo['options'], net)
            except OSError as e:
                logger.error("Exit status {1} during nmap scan on host {0}: {2}".format(host.getID(), e.errno, e.strerror))
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