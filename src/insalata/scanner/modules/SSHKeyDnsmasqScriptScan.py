from insalata.scanner.modules import base
from insalata.model.Host import Host
from insalata.model.Interface import Interface
from insalata.model.DnsService import DnsService
from insalata.model.Layer3Address import Layer3Address
import re
import itertools

def scan(graph, connectionInfo, logger, thread):
    """
    Get DNS information. Information is stord in networks.
    This scanner uses SSH.

    :param graph: Data Interface object for this collector
    :type graph: :class: `Graph`

    :param connectionInfo: Configuration of this collector -> Login information
    :type connectionInfo: dict

    :param logger: The logger this collector shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """
    logger.info("Collecting DNS information")

    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    for host in graph.getAllNeighbors(Host):
        if not ((host.getPowerState() is None) or (host.getPowerState() == 'Running')):
            continue
        ssh = base.getSSHConnection(host)
        logger.debug("Starting DNS scan on host: {0}".format(host.getID()))
        if ssh is None: #No ssh connecton is possible -> Skip this host
            logger.info("Skipping host {0} as ssh connection failed in DNS scan.".format(host.getID()))
            continue

        dnsInformation = ssh.getDNSInfo()
        if not dnsInformation:
            logger.debug("No DNS information available for host {0}".format(host.getID()))
            continue
        if 'domain' not in list(dnsInformation.keys()):
            #No domain -> No DNS server
            continue

        domain = dnsInformation['domain']

        hostInterfaces = host.getAllNeighbors(Interface)
        for interface in list(dnsInformation['interfaces'].keys()):
            if interface == 'delimiter' or interface == "lo":
                continue
            mac = dnsInformation['interfaces'][interface]
            interface = [i for i in hostInterfaces if i.getMAC() == mac]
            if len(interface) == 0:
                logger.error("No interface found for DNSInterface with mac {0} on host {1}.".format(mac, host.getID()))
                continue
            interface = interface[0]


            for address in interface.getAllNeighbors(Layer3Address):
                service = graph.getOrCreateDnsService(name, timeout, address)
                service.setDomain(domain)
                service.verify(name, timeout)
                address.addService(service, name, timeout)

        base.releaseSSHConnection(ssh)
