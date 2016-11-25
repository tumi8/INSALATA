from insalata.model.Node import Node
from insalata.model.Interface import Interface
from xml.etree.ElementTree import SubElement
from insalata.model.Edge import Edge
from insalata.model.PartOfEdge import PartOfEdge
from insalata.model.Layer3Network import Layer3Network



class Layer3Address(Node):
    def __init__(self, address, netmask=None, gateway=None, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.address = address
        self.netmask = netmask
        self.gateway = gateway
        self.static = False

    def getID(self):
        return self.address
    def getGlobalID(self):
        return self.getInterface().getGlobalID() + "_" + self.getID() if self.getInterface() else self.getID()

    def getGateway(self):
        return self.gateway
    def setGateway(self, value, collectorName=None, timeout=None):
        """
        Set the gateway of this address.

        :param value: New gateway
        :type value: str

        :param collectorName: Name of the collector module setting this value
        :type collectorName: str

        :param timeout: Timeout the collecor module uses
        :type timeout: int
        """
        if value != self.getGateway():
            self.gateway = value
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "gateway", "value" : value })
        self.verify(collectorName, timeout)

    def getNetmask(self):
        return self.netmask
    def setNetmask(self, value, collectorName=None, timeout=None):
        """
        Set the netmask of this address.

        :param value: New netmask
        :type value: str

        :param collectorName: Name of the collector module setting this value
        :type collectorName: str

        :param timeout: Timeout the collecor module uses
        :type timeout: int
        """
        if value and value != self.getNetmask():
            self.netmask = value
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "netmask", "value" : value })
        self.verify(collectorName, timeout)

    def getPrefix(self): #generate prefix from decimal dotted netmask string
        return sum([bin(int(x)).count('1') for x in self.netmask.split('.')])

    def addService(self, service, collectorName=None, timeout=None):
        """
        Add a service to this layer 3 address.

        :param service: Service to add to this address
        :type service: insalata.model.Layer3Address.Layer3Address

        :param collectorName: Name of the collector module adding this value
        :type collectorName: str

        :param timeout: Timeout the collecor module uses
        :type timeout: int
        """
        if not service:
            return
        if service not in self.getAllNeighbors(Service):
            PartOfEdge(service, self, collectorName=collectorName, timeout=timeout, association="service", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == service]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getServices(self):
        return self.getAllNeighbors(Service)

    def getInterface(self):
        interfaces = self.getAllNeighbors(Interface)
        return list(interfaces)[0] if len(interfaces) > 0 else None

    def getStatic(self):
        return self.static
    def setStatic(self, value, collectorName=None, timeout=None):
        """
        Define if this address is configured statically on the host.

        :param value: Boolean if the address is configured statically
        :type value: bool

        :param collectorName: Name of the collector module setting this value
        :type collectorName: str

        :param timeout: Timeout the collecor module uses
        :type timeout: int
        """
        if self.getStatic() != value:
            self.static = value
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "static", "value" : value })
        self.verify(collectorName, timeout)

    def getNetwork(self):
        networks = self.getAllNeighbors(type=Layer3Network)
        return list(networks)[0] if len(networks) > 0 else None

    def setNetwork(self, newNetwork, collectorName=None, timeout=None):
        """
        Set the new Layer3Network of this address.
        If other networks are connected, the edges will be deleted.
        If the set network is already the defined one, the edge will be verified by the scanner.

        :param newNetwork: New network of this address
        :type newNetwork: :class: `Layer3Network`

        :param collectorName: Name of the scanner that sets the network
        :type collectorName: str

        :param timeout: Timeout the scanner uses
        :type timeout: int
        """
        if not newNetwork:
            return
        if newNetwork != self.getNetwork():
            for edge in self.getEdges(): #Delete old edges
                if isinstance(edge.getOther(self), Layer3Network):
                    edge.delete(association="network", changed=self)
            Edge(self, newNetwork, collectorName=collectorName, timeout=timeout, association="network", changed=self)
            self.networkId = newNetwork.getID()

        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newNetwork]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)


    def toXML(self, root):
        addressEl = SubElement(root, "layer3address")
        addressEl.attrib["address"] = self.getID()

        servicesEl = SubElement(addressEl, "services")
        if self.getNetmask() != None:
            addressEl.attrib["netmask"] = self.getNetmask()
        if self.getGateway() != None:
            addressEl.attrib["gateway"] = self.getGateway()
        if self.getStatic() is not None:
            addressEl.attrib["static"] = str(self.getStatic())
        if self.getNetwork() is not None:
            addressEl.attrib["network"] = self.getNetwork().getID()

        for service in self.getServices():
            service.toXML(servicesEl)

from insalata.model.Service import Service