from xml.etree.ElementTree import SubElement


from insalata.model.Service import Service


#Represents a DNS server
class DnsService(Service):
    def __init__(self, collectorName=None, timeout=None, address=None):
        Service.__init__(self, 53, "udp", "dns", collectorName=collectorName, timeout=timeout, address=address)
        self.domain = None

    def setDomain(self, newDomain, collectorName=None, timeout=None):
        if newDomain and newDomain != self.getDomain():
            self.domain = newDomain
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "domain", "value" : newDomain })

        self.verify(collectorName, timeout)

    def getDomain(self):
        return self.domain

    #For comparison during diffs:
    def __attrs(self):
        return (self.getID(), self.getType(), self.domain)

    def __eq__(self, other):
        if isinstance(other, DnsService): 
            return self.__attrs() == other.__attrs()
        else:
            return False

    def __hash__(self):
        return hash(self.__attrs())

    #Print information in XML Format
    def toXML(self, root):
        dnsSEl = SubElement(root, "dns")
        if (self.domain is not None):
            dnsSEl.attrib["domain"] = self.domain

        if self.getProduct() is not None:
            dnsSEl.attrib["product"] = self.getProduct()

            if self.getVersion() is not None:
                dnsSEl.attrib["version"] = self.getVersion()
