from xml.etree.ElementTree import SubElement
from insalata.model.Service import Service

class DhcpService(Service):
    """
    This class represents a DHCP-Service in the data model.
    """
    def __init__(self, collectorName=None, timeout=None, address=None):
        """
        Create a new DhcpService with the given parameters.

        :param collectorName: Name of the scanner created this Service
        :type collectorName: str

        :param timeout: Timeout the scanner uses.
        :type timeout: int
        """
        Service.__init__(self, 67, "udp", "dhcp", collectorName=collectorName, timeout=timeout, address=address)

        self.lease = None
        self.start = None
        self.end = None
        self.announcedGateway = None

    def setLease(self, newLease, collectorName=None, timeout=None):
        if newLease and newLease != self.getLease():
            self.lease = newLease
            self.getOnChangeEvent().trigger(self, { "type" : "set",  "member"  : "lease", "value" : newLease })

        self.verify(collectorName, timeout)

    def getLease(self):
        return self.lease

    def getStart(self):
        return self.start

    def getEnd(self):
        return self.end

    def setStartEnd(self, start, end, collectorName=None, timeout=None):
        if start and start != self.getStart():
            self.start = start
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "start", "value" : start })
        if end and end != self.getEnd():
            self.end = end
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "end", "value" :  end})

        self.verify(collectorName, timeout)

    def getDhcpRangeStart(self):
        """
        Get the start index for the DHCP range.

        :returns: The index of the first address to use for DHCP.
        :rtype: int
        """
        netip = self.getIp().getNetwork().getAddress()
        return ipAddressHelper.getIpAddressDifference(self.start, netip)

    def getDhcpRangeEnd(self):
        """
        Get the last index for the DHCP range.

        :returns: The index of the last address to use for DHCP.
        :rtype: int
        """
        broadcast = ipAddressHelper.getBroadcastAddress(self.getIp().getNetwork().getAddress(), self.getIp().getNetwork().getNetmask())
        return ipAddressHelper.getIpAddressDifference(self.end, broadcast) - 1 #starts at 256

    def getAnnouncedGateway(self):
        return self.announcedGateway

    def setAnnouncedGateway(self, gateway, collectorName=None, timeout=None):
        if gateway and gateway != self.getAnnouncedGateway():
            self.announcedGateway = gateway
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "announcedGateway", "value" :  gateway})

        self.verify(collectorName, timeout)

    #For comparison during diffs:
    def __attrs(self):
        return (self.getID(), self.getType(), self.lease, self.start, self.end, self.announcedGateway)

    def __eq__(self, other):
        if isinstance(other, DhcpService): 
            return self.__attrs() == other.__attrs()
        else:
            return False
            
    def __hash__(self):
        return hash(self.__attrs())

    # Have to add interface member at DHCP Server and change to XML method
    #Print information in XML Format
    def toXML(self, root):
        #Create all required XMLTree elements
        dhcpEl = SubElement(root, "dhcp")

        if self.lease is not None:
            dhcpEl.attrib["lease"] = self.getLease()
        if self.start is not None and self.end is not None:
            dhcpEl.attrib["from"] = self.getStart()
            dhcpEl.attrib["to"] = self.getEnd()
        if self.announcedGateway is not None:
            dhcpEl.attrib["announcedGateway"] = self.getAnnouncedGateway()

        if self.getProduct() is not None:
            dhcpEl.attrib["product"] = self.getProduct()

            if self.getVersion() is not None:
                dhcpEl.attrib["version"] = self.getVersion()

from insalata.helper import ipAddressHelper