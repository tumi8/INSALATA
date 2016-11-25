from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node
from insalata.model.Edge import Edge

#Container for routes of a router
class FirewallRaw(Node):
    def __init__(self, firewall, data=None, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.firewall = firewall

        #remove left whitespaces on each line
        ls = [l.lstrip(' ') for l in data.splitlines()]
        self.data = "\n".join(ls[1:])

    def getID(self):
        return self.firewall

    def getGlobalID(self):
        return (self.getHost().getID() + "_" + self.getID()) if self.getHost() else self.getID()

    def getFirewall(self):
        return self.firewall

    def getData(self):
        return self.data

    def setData(self, data, collectorModule, timeout):
        if data != self.getData():
            self.data = data
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "data", "value" : str(data) })

        self.verify(collectorModule, timeout)

    def getHost(self):
        hosts = self.getAllNeighbors(Host)
        return list(hosts)[0] if len(hosts) > 0 else None

    def __attrs(self):
        return (self.firewall, self.data)

    def __eq__(self, other):
        if isinstance(other, FirewallRaw): 
            return self.__attrs() == other.__attrs()
        else:
            return False

    def __hash__(self):
        return hash(self.__attrs())

    #Print information to XML
    def toXML(self, root):
        rawEl = SubElement(root, "raw")
        rawEl.attrib["firewall"] = self.firewall
        rawEl.text = self.data

from insalata.model.Host import Host