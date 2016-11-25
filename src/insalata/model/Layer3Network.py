from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node
from insalata.helper import ipAddressHelper

class Layer3Network(Node):
    def __init__(self, id, address, netmask, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)
        self.__id = id
        self.netmask = netmask
        self.address = address

    def getID(self):
        return self.__id
    def getGlobalID(self):
        return self.getID()

    def getAddress(self):
        return self.address

    def setAddress(self, address, collectorName=None, timeout=None):
        if self.getAddress() != address:
            self.address = address
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "address", "value" : address })
        self.verify(collectorName, timeout)

    def getNetmask(self):
        return self.netmask
    def setNetmask(self, value, collectorName=None, timeout=None):
        """
        Change the netmask of this network.

        :param value: New netmask
        :type value: str

        :param collectorName: Name of the collector module setting this value
        :type collectorName: str

        :param timeout: Timeout the collecor module uses
        :type timeout: int
        """
        if (value is not None) and (self.getNetmask() != value):
            self.netmask = value
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "netmask", "value" : value })
        self.verify(collectorName, timeout)

    def getPrefix(self): #generate prefix from decimal dotted netmask string
        return ipAddressHelper.getPrefix(self.getNetmask())

    #Delete stored environments due to new scan
    def delConfigurations(self, collectorName=None, timeout=None):
        self.__configNames = set()
        self.verify(collectorName, timeout)

    #Print information in XML Format
    def toXML(self, root):
        #Create all needed XMLTree elements
        networkEl = SubElement(root, "layer3network")

        #Add the items which are availabe
        networkEl.attrib["id"] = self.getID()
        networkEl.attrib["netmask"] = self.getNetmask()
        networkEl.attrib["address"] = self.getAddress()
