from xml.etree.ElementTree import SubElement
import sys
import time
import json
from insalata.model.Node import Node
from insalata.model.Edge import Edge
from insalata.model.Location import Location
from insalata.model.Template import Template
from insalata.model.PartOfEdge import PartOfEdge

DEFAULT_TEMPLATE = "host_base"

class Host(Node):
    def __init__(self, id, location = None, template = None, collectorName=None, timeout=None):
        """
        Create a new host object.

        Keyword arguments:
            id -- Name of this host.
            location -- Location of this host. In Xen environment: Xen Server.
            template -- Template used to clone this host.
            collectorName -- Scanner that verifies the new host.
            timeout -- Timeout to delete the new host without new verify
        """
        Node.__init__(self, collectorName=collectorName, timeout=timeout)

        self.__id = id
        self.cpus = None
        self.cpuSpeed = None
        self.memoryMax = None
        self.memoryMin = None
        self.powerState = None

        self.__configNames = set()
        self.__nameApplied = not (self.__id == template)

        if location:
            Edge(self, location, collectorName=collectorName, timeout=timeout, association="location", changed=self)

        if template:
            PartOfEdge(template, self, collectorName=collectorName, timeout=timeout, association="template", changed=self)

    def getID(self):
        return self.__id
    def getGlobalID(self):
        return self.getID()

    def getTemplate(self):
        templates = self.getAllNeighbors(type=Template)
        return list(templates)[0] if len(templates) > 0 else (self.getLocation().getDefaultTemplate() if self.getLocation() else None) 

    def setTemplate(self, newTemplate, collectorName=None, timeout=None):
        """
        Set the template this host is build on.

        :param newTemplate: New template a collector found
        :type newTemplate: insalata.model.Template.Template

        :param collectorName: Name of the collector module setting the template
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if newTemplate and (len(self.getAllNeighbors(type=Template)) == 0 or newTemplate != self.getTemplate()):
            for edge in self.getEdges():
                if isinstance(edge.getOther(self), Template):
                    edge.delete()
            PartOfEdge(newTemplate, self, collectorName=collectorName, timeout=timeout, association="template", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newTemplate]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getLocation(self):
        locations = self.getAllNeighbors(type=Location)
        return list(locations)[0] if len(locations) > 0 else None

    def setLocation(self, newLocation, collectorName=None, timeout=None):
        """
        Set the location this host is build on.

        :param location: New location a collector found
        :type location: insalata.model.Location.Location

        :param collectorName: Name of the collector module setting the location
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if newLocation and newLocation != self.getLocation():
            for edge in self.getEdges():
                if isinstance(edge.getOther(self), Location):
                    edge.delete()
            Edge(self, newLocation, collectorName=collectorName, timeout=timeout, association="location", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newLocation]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getCPUs(self):
        return int(self.cpus) if self.cpus else None
    def setCPUs(self, newCPUs, collectorName=None, timeout=None):
        """
        Set the number of cpus of this host.

        :param newCPUs: New cpus value
        :type newCPUs: int

        :param collectorName: Name of the collector module setting the CPU count
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        newCPUs = int(newCPUs) 
        if newCPUs and newCPUs != self.getCPUs():
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "cpu", "value" :  newCPUs})
            self.cpus = newCPUs
        self.verify(collectorName, timeout)

    def getMemory(self):
        return (int(self.memoryMin) if self.memoryMin else None, int(self.memoryMax) if self.memoryMax else None)

    def setMemory(self, newMin, newMax, collectorName=None, timeout=None):
        """
        Set the memory of this host.

        :param newMin: Minimal memory value
        :type newMax: int

        :param newMax: Maximal memory value
        :type newMax: int

        :param collectorName: Name of the collector module setting the memory
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        newMax = int(newMax)
        newMin = int(newMin)
        if newMin and newMin != self.getMemory()[0]:
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "memoryMin", "value" :  newMin})
            self.memoryMin = int(newMin)

        if newMax and newMax != self.getMemory()[1]:
            self.memoryMax = int(newMax)
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member"  : "memoryMax", "value" : str(newMax) })

        self.verify(collectorName, timeout)

    def addInterface(self, newInterface, collectorName=None, timeout=None):
        """
        Add an interface to this host.

        :param newInterface: Interface to add
        :type newInterface: insalata.model.Interface.Interface

        :param collectorName: Name of the collector module setting the interface
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        edges = [e for e in self.getEdges() if e.getOther(self) == newInterface]
        if len(edges) == 0:
            PartOfEdge(newInterface, self, collectorName=collectorName, timeout=timeout, association="interface", changed=self)
        else:
            for edge in edges:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getInterfaces(self):
        return self.getAllNeighbors(Interface)

    def addRoute(self, newRoute, collectorName=None, timeout=None):
        """
        Add a route to this host.

        :param newRoute: Route to add
        :type newRoute: insalata.model.Route.Route

        :param collectorName: Name of the collector module setting the route
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if newRoute not in self.getAllNeighbors(Route):
            PartOfEdge(newRoute, self, collectorName=collectorName, timeout=timeout, association="route", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newRoute]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getRoutes(self):
        return self.getAllNeighbors(Route)

    def getFirewallRules(self):
        return self.getAllNeighbors(FirewallRule)

    def getFirewallRaw(self):
        raw = self.getAllNeighbors(type=FirewallRaw)
        return list(raw)[0] if len(raw) > 0 else None

    def addFirewallRule(self, newRule, collectorName=None, timeout=None):
        """
        Add a firewall rule to this host.

        :param newRule: Rule to add
        :type newRule: insalata.model.FirewallRule.FirewallRule

        :param collectorName: Name of the collector module setting the firewall rule
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if newRule not in self.getAllNeighbors(FirewallRule):
            PartOfEdge(newRule, self, collectorName=collectorName, timeout=timeout, association="firewallRule", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == newRule]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def setFirewallRaw(self, raw, collectorName=None, timeout=None):
        """
        Set the raw firewall dump for this host.

        :param raw: Raw firewall data to set
        :type raw: insalata.model.FirewallRaw.FirewallRaw

        :param collectorName: Name of the collector module setting the raw data
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if raw not in self.getAllNeighbors(FirewallRaw):
            for edge in [e for e in self.getEdges() if isinstance(e, FirewallRaw)]:
                edge.delete(association="firewallRaw", changed=self)
            PartOfEdge(raw, self, collectorName=collectorName, timeout=timeout, association="firewallRaw", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == raw]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def addDisk(self, disk, collectorName=None, timeout=None):
        """
        Add a disk to this host.

        :param disk: Rule to add
        :type disk: insalata.model.Disk.Disk

        :param collectorName: Name of the collector module setting the disk
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if disk not in self.getAllNeighbors(Disk):
            PartOfEdge(disk, self, collectorName=collectorName, timeout=timeout, association="disk", changed=self)
        else:
            for edge in [e for e in self.getEdges() if e.getOther(self) == disk]:
                edge.verify(collectorName, timeout)
        self.verify(collectorName, timeout)

    def getDisks(self):
        return self.getAllNeighbors(Disk)

    def getConfigNames(self):
        return frozenset(self.__configNames)

    def setConfigNames(self, configs, collectorName=None, timeout=None):
        """
        Set the configurations

        :param configs: Configurations this host is contained in
        :type configs: list<str>

        :param collectorName: Name of the collector module adding the configuration
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if configs != list(self.getConfigNames()):
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "configurations", "value" : str(configs) })
            self.__configNames = configs
        self.verify(collectorName, timeout)

    def setPowerState(self, powerState, collectorName=None, timeout=None):
        """
        Change the power state of this host.

        :param powerState: New power state
        :type powerState: str

        :param collectorName: Name of the collector module adding the configuration
        :type collectorName: str

        :param timeout: Timeout the collector uses
        :type timeout: int
        """
        if self.getPowerState() != powerState:
            self.powerState = powerState
            self.getOnChangeEvent().trigger(self, { "type" : "set", "member" : "powerState", "value" : powerState })
        self.verify(collectorName, timeout)

    def getPowerState(self):
        return self.powerState

    def getDefaultDiskName(self):
        return self.getID() + "-hdd"

    #indicates whether or not the machine can be reached under it's ID (== True)
    #new machines after cloning have 'false' here, the first reboot after naming them sets it to 'true'
    def getNameApplied(self):
        return self.__nameApplied
    def setNameApplied(self, value):
        self.__nameApplied = value

    #Output data in XML Format
    def toXML(self, root):
        hostEl = SubElement(root, "host")
        hostEl.attrib["id"] = self.getID()

        if(self.getMemory()[0] is not None and self.getMemory()[1] is not None):
            hostEl.attrib["memoryMin"] = str((self.getMemory())[0])
            hostEl.attrib["memoryMax"] = str((self.getMemory())[1])

        if(self.getCPUs() is not None):
            hostEl.attrib["cpus"] = str(self.getCPUs())

        if(self.getLocation() is not None):
            hostEl.attrib["location"] = self.getLocation().getID()

        if (self.getTemplate() is not None):
            hostEl.attrib["template"] = self.getTemplate().getID()
        else:
            hostEl.attrib["template"] = DEFAULT_TEMPLATE
        if self.getPowerState() is not None:
            hostEl.attrib["powerState"] = self.getPowerState()

        interfacesEl = SubElement(hostEl, "interfaces")
        disksEl = SubElement(hostEl, "disks")
        routesEl = SubElement(hostEl, "routes")
        firewallEl = SubElement(hostEl, "firewall")
        firewallRulesEl = SubElement(firewallEl, "firewallRules")

        for route in self.getRoutes():
            route.toXML(routesEl)

        for rule in self.getFirewallRules():
            rule.toXML(firewallRulesEl)
        if self.getFirewallRaw():
            self.getFirewallRaw().toXML(firewallRulesEl)

        for interface in self.getInterfaces():
            if not (interface.getNetwork() == 'controll-network'):
                interface.toXML(interfacesEl)

        for disk in self.getDisks():
            disk.toXML(disksEl)


from insalata.model.Interface import Interface
from insalata.model.Route import Route
from insalata.model.FirewallRule import FirewallRule
from insalata.model.FirewallRaw import FirewallRaw
from insalata.model.Disk import Disk
