from insalata.scanner.modules import base
from insalata.model.Route import Route
from insalata.model.Host import Host
from insalata.model.Interface import Interface

import re


def scan(graph, connectionInfo, logger, thread):
    """
    Get all routes from software routers in the network.
    Method uses SSH over keys and a host Script on the template to get the routes.

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
    logger.info("Collecting routing information.")

    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    for host in graph.getAllNeighbors(Host):
        if not ((host.getPowerState() is None) or (host.getPowerState() == 'Running')):
            continue
        ssh = base.getSSHConnection(host)
        if ssh is None: #No ssh connecton is possible -> Skip this host
            logger.info("Skipping host {0} as ssh connection failed in Routing scan.".format(host.getID()))
            continue

        hostInterfaces = host.getAllNeighbors(Interface)
        currentHostRoutes = set(host.getAllNeighbors(Route))

        routingInformation = ssh.getRoutingInfo()
        if not routingInformation:
            logger.debug("No routing informaiton available for host {}".format(host.getID()))
            continue
        routingInfo = ssh.getRoutingInfo()
        if not routingInfo:
            logger.debug("No routing information (None) for host. '{}'".format(host.getID()))
            continue
        for entry in routingInfo:
            if "delimiter" in list(entry.keys()) or entry['gateway'] == "0.0.0.0": #No routes in directly connected networks should be depicted
                continue
            interface = [i for i in hostInterfaces if i.getMAC() == entry['mac']]
            if len(interface) == 0:
                logger.error("No interface found with mac {0} on host {1}. Maybe this is docker's bridging interface.".format(entry['mac'], host.getID()))
                continue
            interface = interface[0]

            route = graph.getOrCreateRoute(name, timeout, host, entry['destination'], entry['genmask'], entry['gateway'], interface=None)
            currentHostRoutes.discard(route)

            host.addRoute(route)

            route.setInterface(interface)

        for route in currentHostRoutes:
            route.removeVerification(name)

        base.releaseSSHConnection(ssh)

