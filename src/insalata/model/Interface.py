from xml.etree.ElementTree import SubElement
from insalata.model.Layer2Network import Layer2Network
from insalata.model.Node import Node
from insalata.model.Edge import Edge
from insalata.model.PartOfEdge import PartOfEdge

class Interface(Node):

    def __init__(self, mac, network=None, collectorName=None, timeout=None):
        """
        Method creating new interface opject.

        :param mac: MAC-address of this interface. (Used as identifier)
        :type mac: str

        :param network: 'Network' object this interface is connected to
        :type network: insalata.model.Layer2Network
        """
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.__mac = mac
        self.networkId = None
        self.rate = None # In kbps
        self.mtu = None

        if network:
            Edge(self, network, collectorName=collectorName, timeout=timeout)
            self.networkId = network.getID()

    def getID(self):    #a canonical id for diffs (basically the order)
        return "enx" + self.getMAC().replace(':', '')

    def getGlobalID(self):
        return self.getID()

    def getNetwork(self):
        networks = self.getAllNeighbors(type=Layer2Network)
        return list(networks)[0] if len(networks) > 0 else None

    def setNetwork(self, newNetwork, collectorName=None, timeout=None):
        """
        Set the network of this interface.

        :param newNetwork: New network
        :type newNetwork: insalata.model.Layer2Network.Layer2Network

        :param collectorName: Name of the collector module setting the network
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if not newNetwork:
            return
        if newNetwork != self.getNetwork():
            for edge in self.getEdges(): #Delete old edges
                if isinstance(edge.getOther(self), Layer2Network):
                    edge.delete(association="network", changed=self)
            Edge(self, newNetwork, collectorName=collectorName, timeout=timeout, association="network", changed=self)
            self.networkId = newNetwork.getID()

        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newNetwork]:
                edge.verify(collectorName, timeout)

        self.verify(collectorName, timeout)

    def getMAC(self):
        return self.__mac
        
    def getRate(self):
        return int(self.rate) if self.rate else None
    def setRate(self, newRate, collectorName=None, timeout=None):
        newRate = int(newRate)
        """
        Set the rate limit of this interface.

        :param newRate: Rate of the interface
        :type newRate: int

        :param collectorName: Name of the collector module setting the rate
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if self.getRate() != newRate:
            self.rate=newRate
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "rate", "value" : newRate })
        self.verify(collectorName, timeout)

    def getAddresses(self):
        return self.getAllNeighbors(type = Layer3Address)

    def addAddress(self, address, collectorName=None, timeout=None):
        """
        Add a Layer3Address object to this interface.

        :param address: The layer 3 address object which shall be connected to the interface
        :param type: insalata.model.Layer3Address.Layer3Address

        :param collectorName: Name of the collector module setting the address
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if address not in self.getAllNeighbors(Layer3Address):
            PartOfEdge(address, self, collectorName=collectorName, timeout=timeout, association="address", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == address]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getMtu(self):
        return int(self.mtu) if self.mtu else None
    def setMtu(self, mtu, collectorName=None, timeout=None):
        """
        Set the MTU of this interface.

        :param mtu: The MTU used by this interface
        :type mtu: int

        :param collectorName: Name of the collector module setting the MTU
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        mtu = int(mtu)
        if self.getMtu() != mtu:
            self.mtu = mtu
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "mtu", "value" : mtu })
        self.verify(collectorName, timeout)


    def isDhcp(self):
        if len(self.getAddresses()) > 0:
            return any(not ip.getStatic() for ip in self.getAddresses())
        else:
            return True

    def getHost(self):
        hosts = self.getAllNeighbors(Host)
        return list(hosts)[0] if len(hosts) > 0 else None

    def setHost(self, newHost, collectorName=None, timeout=None):
        """
        Set the host containing this interface.

        :param newHost: Host containing the interface
        :type newHost: insalata.model.Host.Host

        :param collectorName: Name of the collector module setting the host
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if not newHost:
            return
        if newHost not in self.getAllNeighbors(Host):
            for edge in self.getEdges():
                if isinstance(edge.getOther(self), Host):
                    edge.delete(association="host", changed=self)
            Edge(self, newHost, collectorName=collectorName, timeout=timeout, association="host", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newHost]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    #For comparison during diffs:
    def __attrs(self):
        return (self.networkId, self.__mac, self.rate, self.mtu)

    def __eq__(self, other):
        if isinstance(other, Interface):
            return self.__attrs() == other.__attrs()
        else:
            return False

    def __hash__(self):
        return hash(self.__attrs())


    #Print information in XML Format
    def toXML(self, root):
        interfaceEl = SubElement(root , "interface")

        interfaceEl.attrib["mac"] = str(self.getMAC())
        if self.getNetwork() is not None:
            interfaceEl.attrib["network"] = self.getNetwork().getID()
        if self.getRate()!=None:
            interfaceEl.attrib["rate"] = str(self.getRate())
        if self.getMtu()!=None:
            interfaceEl.attrib["mtu"] = str(self.getMtu())

        for address in self.getAddresses():
            address.toXML(interfaceEl)

from insalata.model.Layer3Address import Layer3Address
from insalata.model.Host import Host