from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node
from insalata.model.Edge import Edge
from insalata.model.Host import Host

class Route(Node):
    def __init__(self, dest, gen, gateway, interface=None, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.destination = dest
        self.genmask = gen
        self.gateway = gateway

        if interface:
            self.setInterface(interface, collectorName, timeout)

    def getID(self):
        return str(self.__hash__())

    def getGlobalID(self):
        hosts = list(self.getAllNeighbors(Host))
        if len(hosts) == 0:
            return self.getID()
        return hosts[0].getID() + "_" + self.getID()

    def getDestination(self):
        return self.destination

    def getGenmask(self):
        return self.genmask

    def getInterface(self):
        interfaces = self.getAllNeighbors(type = Interface)
        return list(interfaces)[0] if len(interfaces) > 0 else None

    def setInterface(self, newInterface, collectorName=None, timeout=None):
        if not newInterface:
            return
        edges = [e for e in self.getEdges() if isinstance(e.getOther(self), Interface)]
        if len(edges) > 0 and (edges[0].getOther(self) == newInterface):
            edges[0].verify(collectorName, timeout)
        else:
            for edge in edges:
                edge.delete(association="interface", changed=self)
            Edge(self, newInterface, collectorName=collectorName, timeout=timeout, association="interface", changed=self)


    def getGateway(self):
        return self.gateway

    def getPrefix(self):
        return sum([bin(int(x)).count('1') for x in self.genmask.split('.')])

    def __attrs(self):
        return (self.destination, self.genmask)

    def __eq__(self, other):
        if isinstance(other, Route): 
            return self.__attrs() == other.__attrs()
        else:
            return False

    def __hash__(self):
        return hash(self.__attrs())

    #Print information to XML
    def toXML(self, root):
        routeEl = SubElement(root, "route")
        if(self.destination is not None):
            routeEl.attrib["destination"] = self.destination
        if(self.genmask is not None):
            routeEl.attrib["genmask"] = self.genmask
        if(self.gateway is not None):
            routeEl.attrib["gateway"] = self.gateway
        if(self.getInterface() is not None):
            routeEl.attrib["interface"] = self.getInterface().getID()

from insalata.model.Interface import Interface