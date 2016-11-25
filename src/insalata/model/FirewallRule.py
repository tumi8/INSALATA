from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node
from insalata.model.Edge import Edge
from insalata.model.Host import Host

#Container for routes of a router
class FirewallRule(Node):
    def __init__(self, chain, action, protocol, srcnet=None, destnet=None, srcports=None, destports=None, inInterface=None, outInterface=None, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.chain = chain
        self.action = action
        self.protocol = protocol
        self.srcnet = srcnet
        self.destnet = destnet
        self.srcports = srcports
        self.destports = destports

        if outInterface:
            Edge(self, outInterface, collectorName, timeout, association="outInterface", changed=self, name="outInterface")

        if inInterface:
            Edge(self, inInterface, collectorName, timeout, association="inInterface", changed=self, name="inInterface")

    def getID(self):
        return str(self.__hash__())

    def getGlobalID(self):
        hosts = list(self.getAllNeighbors(Host))
        if len(hosts) == 0:
            return self.getID()
        return hosts[0].getID() + "_" + self.getID()

    def setInInterface(self, newInterface, collectorName=None, timeout=None):
        """
        Set the inInterface of this firewall rule.

        :param newInterface: New Interface
        :type interface: insalata.model.Interface.Interface

        :param collectorName: Name of the collector module setting the interface
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if self.getInInterface() != newInterface:
            for edge in [e for e in self.getEdges() if e.getName() and e.getName() == "inInterface"]:
                edge.delete(association = "inInterface", changed = self)
            Edge(self, newInterface, collectorName, timeout, association="inInterface", changed=self, name="inInterface")
        else:
            for edge in [e for e in self.getEdges() if e.getName()=="inInterface"]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def setOutInterface(self, newInterface, collectorName=None, timeout=None):
        """
        Set the outInterface of this firewall rule.

        :param newInterface: New Interface
        :type interface: insalata.model.Interface.Interface

        :param collectorName: Name of the collector module setting the interface
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if self.getOutInterface() != newInterface:
            for edge in [e for e in self.getEdges() if e.getName() and e.getName() == "outInterface"]:
                edge.delete(association = "outInterface", changed = self)
            Edge(self, newInterface, collectorName, timeout, association="outInterface", changed=self, name="outInterface")
        else:
            for edge in [e for e in self.getEdges() if e.getName()=="outInterface"]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getInInterface(self):
        interfaces = [e for e in self.getEdges() if e.getName() and e.getName() == "inInterface"]
        return interfaces[0] if len(interfaces) > 0 else None

    def getOutInterface(self):
        interfaces = [e for e in self.getEdges() if e.getName() and e.getName() == "outInterface"]
        return interfaces[0] if len(interfaces) > 0 else None

    def getChain(self):
        return self.chain

    def getAction(self):
        return self.action

    def getProtocol(self):
        return self.protocol

    def getSrcNet(self):
        return self.srcnet

    def getDestNet(self):
        return self.srcnet

    def getSrcPorts(self):
        return self.srcports

    def getDestPorts(self):
        return self.destports

    def __attrs(self):
        return (self.chain, self.action, self.protocol, self.srcnet, self.destnet, self.srcports, self.destports)

    def __eq__(self, other):
        if isinstance(other, FirewallRule): 
            return self.__attrs() == other.__attrs()
        else:
            return False

    def __hash__(self):
        return hash(self.__attrs())

    #Print information to XML
    def toXML(self, root):
        ruleEl = SubElement(root, "rule")
        if(self.chain is not None):
            ruleEl.attrib["chain"] = self.chain
        if(self.action is not None):
            ruleEl.attrib["action"] = self.action
        if(self.protocol is not None):
            ruleEl.attrib["protocol"] = self.protocol
        if(self.srcnet is not None):
            ruleEl.attrib["srcnet"] = self.srcnet
        if(self.destnet is not None):
            ruleEl.attrib["destnet"] = self.destnet
        if(self.getSrcPorts() is not None):
            if len(self.getSrcPorts() > 1):
                ruleEl.attrib["srcports"] = str(self.getSrcPorts()[0]) + ":" + str(self.getSrcPorts()[-1])
            else:
                ruleEl.attrib["srcports"] = str(self.getSrcPorts()[0])
        if(self.getDestPorts() is not None):
            if len(self.getDestPorts() > 1):
                ruleEl.attrib["destports"] = str(self.getDestPorts()[0]) + ":" + str(self.getDestPorts()[-1])
            else:
                ruleEl.attrib["destports"] = str(self.getDestPorts()[0])
        if(self.getInInterface() is not None):
            ruleEl.attrib["inInterface"] = self.getInInterface().getID()
        if(self.getOutInterface() is not None):
            ruleEl.attrib["outInterface"] = self.getOutInterface().getID()

from insalata.model.Interface import Interface