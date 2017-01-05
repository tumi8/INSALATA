import re
from insalata.model.Host import Host
from insalata.model.Interface import Interface
from insalata.model.Layer3Address import Layer3Address
from insalata.scanner.modules import base

def scan(graph, connectionInfo, logger, thread):
    """
    Get DHCP information from each Host by using SSH and login with key.

    Necessary values in the configuration file of this collector module:
        - timeout       Timeout this collector module shall use (Integer)
    
    :param graph: Data interface object for this collector module
    :type graph: insalata.model.Graph.Graph

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: logging:Logger

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """
    logger.info("Collection DHCP information")

    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    for host in graph.getAllNeighbors(Host):
        if not ((host.getPowerState() is None) or (host.getPowerState() == 'Running')):
            continue
        ssh = base.getSSHConnection(host)
        logger.debug("Starting DHCP scan on host: {0}".format(host.getID()))
        if ssh is None: #No ssh connecton is possible -> Skip this host
            logger.info("Skipping host {0} as ssh connection failed in DHCP scan.".format(host.getID()))
            continue

        dhcpInformation = ssh.getDHCPInfo()
        if not dhcpInformation:
            logger.debug("No DHCP information available for host {0}".format(host.getID()))
            continue
        
        hostInterfaces = host.getAllNeighbors(Interface)
        for mac in list(dhcpInformation['ranges'].keys()):
            if mac == "delimiter":
                continue
            interface = [i for i in hostInterfaces if i.getMAC() == mac]
            if len(interface) == 0:
                logger.error("No interface found for DHCPInterface with mac {0} on host {1}.".format(mac, host.getID()))
                continue
            interface = interface[0]

            gateway = None
            if mac in (list(dhcpInformation['options'].keys())) and ("announced_gateway" in list(dhcpInformation['options'][mac].keys())):
                gateway = dhcpInformation['options'][mac]["announced_gateway"]

            lease = dhcpInformation['ranges'][mac]['lease']
            start = dhcpInformation['ranges'][mac]['from']
            end = dhcpInformation['ranges'][mac]['to']

            for address in interface.getAllNeighbors(Layer3Address):
                service = graph.getOrCreateDhcpService(name, timeout, address)
                service.setStartEnd(start, end, name, timeout)
                service.setLease(lease, name, timeout)
                if gateway:
                    service.setAnnouncedGateway(gateway, name, timeout)
                service.verify(name, timeout)
                address.addService(service, name, timeout)
            
        base.releaseSSHConnection(ssh)