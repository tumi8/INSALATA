from insalata.model.Host import Host
from insalata.helper import SnmpWrapper
from ipaddress import IPv4Address
from insalata.model.Layer3Network import Layer3Network
from insalata.model.Layer2Network import Layer2Network
from insalata.model.Layer3Address import Layer3Address

def scan(graph, connectionInfo, logger, thread):
    """
    """
    logger.info("Converting Layer3Networks to Layer2Networks")
    name = connectionInfo["name"]
    timeout = int(connectionInfo["timeout"])

    currentNetworks = set()
    for l3network in graph.getAllNeighbors(Layer3Network):
        location = graph.getOrCreateLocation("physical", name, timeout)
        l2network = graph.getOrCreateLayer2Network(l3network.getAddress(), name, timeout, location=location)
        currentNetworks.add(l2network.getID())
        l2network.verify(name, timeout)

        interfaces = [a.getInterface() for a in graph.getAllNeighbors(Layer3Address) if a.getNetwork() == l3network]
        for interface in interfaces:
            if not interface:
                continue
            interface.setNetwork(l2network)

        logger.debug("Adding new layer 2 network: {}".format(l2network.getID()))

    for l2network in [n for n in graph.getAllNeighbors(Layer2Network) if n.getID() not in currentNetworks]:
        l2network.removeVerification(name)

    
