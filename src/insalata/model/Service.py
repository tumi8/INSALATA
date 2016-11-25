from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node
from insalata.model.PartOfEdge import PartOfEdge
from insalata.model.Layer3Address import Layer3Address

#represents a service
class Service(Node):
    def __init__(self, port, protocol, type, collectorName=None, timeout=None, address=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.port = port
        self.type = type
        self.protocol = protocol
        self.product = None
        self.version = None
        if address:
            PartOfEdge(self, address, collectorName=collectorName, timeout=timeout)

    def getAddress(self):
        addresses = [a for a in self.getAllNeighbors(Layer3Address)]
        return addresses[0] if len(addresses) > 0 else None

    def setAddress(self, address, collectorName, timeout):
        if not address:
            return
        if address != self.getAddress():
            for edge in self.getEdges(): #Delete old edges
                if isinstance(edge.getOther(self), Layer3Address):
                    edge.delete(association="address", changed=self)
            PartOfEdge(self, address, collectorName=collectorName, timeout=timeout, association="address", changed=self)

        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == address]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)
    
    def getID(self):
        return str(self.port) + "_" + self.protocol + "_" + (self.getProduct() if self.getProduct() else self.getType())

    def getGlobalID(self):
        return self.getIp().getGlobalID() + ":" + str(self.getID()) if self.getIp() else str(self.getID())

    def getPort(self):
        return self.port

    def getProtocol(self):
        return self.protocol

    def setProduct(self, product):
        if self.getProduct() != product:
            self.product = product
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "product", "value" : product })
    def getProduct(self):
        return self.product

    def setVersion(self, version, collectorName=None, timeout=None):
        """
        Set the service version.

        :param version: Version for the service
        :type version: str

        :param collectorName: Name of the collector module setting this value
        :type collectorName: str

        :param timeout: Timeout the collecor module uses
        :type timeout: int
        """
        if self.getVersion() != version:
            self.version = version
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "version", "value" : version })
        self.verify(collectorName, timeout)


    def getVersion(self):
        return self.version

    def getType(self):
        return self.type if self.type else ''

    def setType(self, value, collectorName=None, timeout=None):
        """
        Set the service type.

        :param value: Type for the service
        :type value: str

        :param collectorName: Name of the collector module setting this value
        :type collectorName: str

        :param timeout: Timeout the collecor module uses
        :type timeout: int
        """
        if self.getType() != value:
            self.type = value
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "type", "value" : type })
        self.verify(collectorName, timeout)

    def getIp(self):
        return self.getAddress()

    def getInterface(self):
        ips = self.getAllNeighbors(type=Layer3Address)
        if len(ips) > 0:
            return list(ips)[0].getInterface()
        return None

    def getHost(self):
        return self.getInterface().getHost()

    #Print information in XML Format
    def toXML(self, root):
        #Create all required XMLTree elements
        serviceEl = SubElement(root, "service")
        serviceEl.attrib["port"] = self.getPort()
        serviceEl.attrib["protocol"] = self.getProtocol()

        if self.getType() is not None:
            serviceEl.attrib["type"] = self.getType()

        if self.getProduct() is not None:
            serviceEl.attrib["product"] = self.getProduct()

            if self.getVersion() is not None:
                serviceEl.attrib["version"] = self.getVersion()