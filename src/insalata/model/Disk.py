from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node

class Disk(Node):

    def __init__(self, name, size=None, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.__id = name
        self.__size = size

    def getID(self):
        return self.__id

    def getGlobalID(self):
        #return self.getHost().getGlobalID() + "_" + self.getID() if self.getHost() else self.getID()
        return self.getID()

    def getHost(self):
        hosts = self.getAllNeighbors(Host)
        return list(hosts)[0] if len(hosts) > 0 else None

    def getSize(self):
        return self.__size
    
    def setSize(self, size, collectorName=None, timeout=None):
        if size and size != self.getSize():
            self.__size = size
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "size", "value" : size })
        self.verify(collectorName, timeout)


    def toXML(self, root):
        VDIEl = SubElement(root, "disk")
        if self.getID() != None:
            VDIEl.attrib["id"] = self.getID()
        if self.getSize() != None:
            VDIEl.attrib["size"] = str(self.getSize())


from insalata.model.Host import Host