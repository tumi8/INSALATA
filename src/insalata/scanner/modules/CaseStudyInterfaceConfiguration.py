from insalata.model.Host import Host
from insalata.model.Interface import Interface
from insalata.model.Layer3Address import Layer3Address
from insalata.scanner.modules import base
from insalata.helper import ipAddressHelper
import re

def scan(graph, connectionInfo, logger, thread):
    """
    Get Interface configuration from hosts over ssh. -> MTU, Rate, Ips
    This method uses prepacked scripts on template.
    
    :param graph: Data Interface object for this collector
    :type graph: :class: `Graph`

    :param connectionInfo: Configuration of this collector -> Login information
    :type connectionInfo: dict

    :param logger: The logger this collector shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """


    logger.info("Collecting interface configuration information from Hosts")

    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    for host in graph.getAllNeighbors(Host):
        if not ((host.getPowerState() is None) or (host.getPowerState() == 'Running')):
            continue
        ssh = base.getSSHConnection(host)
        logger.info("Starting interface configuration scan on host: {0}".format(host.getID()))
        if ssh is None: #No ssh connecton is possible -> Skip this host
            logger.info("Skipping host {0} as ssh connection failed.".format(host.getID()))
            continue

        interfaceInformation = ssh.getInterfaceInfo()
        hostInterfaces = host.getAllNeighbors(Interface)
        ansible = base.getAnsibleInfo(host)

        #get Information
        for intf in interfaceInformation:
            if intf['type'] == 'loopback' or intf['mac'] != "00:00:00:00:00:00":
                continue
            interface = graph.getOrCreateInterface(intf['mac'], name, timeout, network=None)
            interface.verify(name, timeout)
            host.addInterface(interface, name, timeout)
            if len(interface) == 0:
                continue
            interface = interface[0]

            interface.setMtu(intf['mtu'], name, timeout)
            try:
                interface.setRate(int(intf['speed']) * 1000, name, timeout)
            except:
                pass #Normal case on virtual interfaces


            stillExistingAddresses = set() # Set of still existing addresses on this host (insalata.model.Layer3Address)
            if isinstance(ansible['ansible_facts']['ansible_'+intf['name']]['ipv4'], list):
                addressesElements = list(ansible['ansible_facts']['ansible_'+intf['name']]['ipv4'])
            else: # Single dict
                addressesElements = [ansible['ansible_facts']['ansible_'+intf['name']]['ipv4']]
            for addressEl in addressesElements:
                netmask = None
                try:
                    interfaceAddress = addressEl['address']
                    netmask = addressEl['netmask']
                except KeyError as e:
                    logger.error("Ansible was not able to detect the {0} on interface {1}".format(e.args[0], intf['name']))
                    continue
                gateway = intf['gateway'] if "gateway" in list(intf.keys()) else None
                address = graph.getOrCreateLayer3Address(interfaceAddress, name, timeout, netmask=netmask, gateway=gateway)
                address.verify(name, timeout)
                interface.addAddress(address)
                stillExistingAddresses.add(address)

            # Remove old addresses
            for old_adr_edge in [e for e in interface.getEdges() if isinstance(e.getOther(interface), Layer3Address) and e.getOther(interface) not in stillExistingAddresses]:
                logger.critical(str(type(old_adr_edge)))
                logger.critical(old_adr_edge.getOther(interface).getID())
                old_adr_edge.removeVerification(name, timeout)
                old_adr_edge.getOther(interface).removeVerification(name, timeout)


            # At the end: Create Layer3networks
            for address in stillExistingAddresses:
                netmask = address.getNetmask()
                if not netmask: # we are not able to determine the network address if no netmask is set => Take /32
                    netmask = "255.255.255.255"
                netAddress = ipAddressHelper.getNetAddress(address.getID(), netmask)
                l3network = graph.getOrCreateLayer3Network(netAddress + "/" + str(ipAddressHelper.getPrefix(netmask)), name, timeout, netAddress, netmask)
                l3network.verify(name, timeout)
                address.setNetwork(l3network)

        base.releaseSSHConnection(ssh)