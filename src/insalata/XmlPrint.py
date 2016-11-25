"""
This modules provides methods to print a configuration to a XML file.
"""
from xml.etree.ElementTree import Element, SubElement, ElementTree

def printXML(file, graph):
    """
    Print the XML for a given graph.

    :param file: File to print the XML into
    :type file: str

    :param graph: Graph coantaining the scanned information
    :type graph: :class:'insalata.model.Graph'
    """
    root = Element("config")
    root.attrib['name'] = graph.getID()
    printLocations(root, graph.getLocations())
    printHosts(root, graph.getHosts())
    printLayer2Networks(root, graph.getL2Networks())
    printLayer3Networks(root, graph.getL3Networks())
    #printVlans(root, graph.getVlan())
    ElementTree(root).write(file)

def printLocations(root, locations):
    """
    Output all location objects contained in the graph.

    :param root: XML element that shall contain the locations
    :type root: :class:'xml.etree.ElementTree.Element'

    :param locations: Location objects to print
    :type locations: set
    """
    if(locations is not None):
        locationsEl = SubElement(root, "locations")
        for location in locations:
            location.toXML(locationsEl)

def printLayer2Networks(root, networks):
    """
    Output all Layer2Network objects contained in the graph.

    :param root: XML element that shall contain the networks
    :type root: :class:'xml.etree.ElementTree.Element'

    :param locations: Layer2Network objects to print
    :type locations: set
    """
    if(networks is not None):
        networksEl = SubElement(root, "layer2networks")

    for network in networks:
        network.toXML(networksEl)

def printLayer3Networks(root, networks):
    """
    Output all Layer3Network objects contained in the graph.

    :param root: XML element that shall contain the networks
    :type root: :class:'xml.etree.ElementTree.Element'

    :param locations: Layer3Network objects to print
    :type locations: set
    """
    if(networks is not None):
        networksEl = SubElement(root, "layer3networks")

        for network in networks:
            network.toXML(networksEl)

def printHosts(root, hosts):
    """
    Output all Host objects contained in the graph.

    :param root: XML element that shall contain the hosts
    :type root: :class:'xml.etree.ElementTree.Element'

    :param locations: Host objects to print
    :type locations: set
    """
    if(hosts is not None):
        hostsEl = SubElement(root, "hosts")
        for host in hosts:
            host.toXML(hostsEl)

def printVlans(root, vlans):
    """
    Output all VLAN objects contained in the graph.
    :note: Obsolete

    :param root: XML element that shall contain the networks
    :type root: :class:'xml.etree.ElementTree.Element'

    :param locations: VLAN objects to print
    :type locations: set
    """
    if(vlans is not None):
        vlanEl = SubElement(root, "vlans")
        for vlan in vlans:
            vlan.toXML(vlanEl)
