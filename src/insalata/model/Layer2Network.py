from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node
from insalata.model.Edge import Edge
from insalata.model.Location import Location

class Layer2Network(Node):
    def __init__(self, id, location=None, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.__id = id
        self.__configNames = set()

        if location is not None:
            Edge(self, location)

    def getID(self):
        return self.__id
    def getGlobalID(self):
        return self.getID()

    def getConfigNames(self):
        return frozenset(self.__configNames)

    def setConfigNames(self, configs, collectorName=None, timeout=None):
        """
        Set the configurations

        :param configs: Configurations this network is contained in
        :type configs: list<str>

        :param collectorName: Name of the collector module adding the configuration
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if list(configs) != list(self.getConfigNames()):
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "configurations", "value" : str(configs) })
            self.__configNames = configs
        self.verify(collectorName, timeout)

    def getLocation(self):
        locations = self.getAllNeighbors(type=Location)
        return list(locations)[0] if len(locations) > 0 else None

    def setLocation(self, newLocation, collectorName=None, timeout=None):
        """
        Set the location containing the layer 2 network.

        :param newLocation: The location object containing the network
        :type newLocation: insalata.model.Location.Location

        :param collectorName: Name of the collector module setting the location
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if newLocation not in self.getAllNeighbors(Location):
            for edge in self.getEdges():
                if isinstance(edge.getOther(self), Location):
                    edge.delete(association="location", changed=self)
            Edge(self, newLocation, collectorName=collectorName, timeout=timeout, association="location", changed=self)

        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newLocation]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    #Print information in XML Format
    def toXML(self, root):
        #Create all needed XMLTree elements
        networkEl = SubElement(root, "layer2network")

        #Add the items which are availabe
        networkEl.attrib["id"] = self.getID()
