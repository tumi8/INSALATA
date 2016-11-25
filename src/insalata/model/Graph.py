#Represents a complete configuration
import insalata.model
from lxml import etree
from insalata.builder.Builder import Builder
from insalata.model.Node import Node
from insalata.model.Event import Event
from functools import partial
import itertools
import threading
import traceback

import logging
import sys
import pkgutil
import importlib

class Graph(Node):
    def __init__(self, id, allL2Networks=set(), allL3Networks=set(), locations=set(), allHosts=set()):
        Node.__init__(self)
        self.id = id
        for host in allHosts:
            Edge(self, host)

        for network in allL2Networks:
            Edge(self, network)

        for network in allL3Networks:
            Edge(self, network)

        for location in locations:
            Edge(self, location)

        self.__locks = {
            Host : threading.Lock(),
            DhcpService : threading.Lock(),
            Disk : threading.Lock(),
            DnsService : threading.Lock(),
            Interface : threading.Lock(),
            Layer2Network : threading.Lock(),
            Layer3Address : threading.Lock(),
            Layer3Network : threading.Lock(),
            Location : threading.Lock(),
            Route : threading.Lock(),
            Service : threading.Lock(),
            FirewallRule : threading.Lock(),
            FirewallRaw : threading.Lock()
        }

        self.__objectChangedEvent = Event()
        self.__objectNewEvent = Event()
        self.__objectDeletedEvent = Event()

        self.__out = open("output.txt", "w")

    def getObjectChangedEvent(self):
        """
        Return the objectChangedEvent of the graph.

        The objectChangedEvent is triggered everytime a object in the graph changes.
        """
        return self.__objectChangedEvent

    def getObjectNewEvent(self):
        """
        Return the objectNewEvent of this node.

        The objectNewEvent is triggered everytime a object is added to the graph.
        """
        return self.__objectNewEvent

    def getObjectDeletedEvent(self):
        """
        Return the objectDeletedEvent of this node.

        The objectDeletedEvent is triggered everytime a object in the graph is deleted.
        """
        return self.__objectDeletedEvent

    def freeze(self):
        """
        Freeze the graph => Pause every Timer of every Node
        """
        for node in self.getAllNeighbors(type=None):
            for timer in node.getTimers():
                timer.pause()
            for edge in node.getEdges():
                for timer in edge.getTimers():
                    timer.pause()

    def melt(self): # ;)
        """
        Unfreeze the graph => Resume every timer of the nodes
        """
        for node in self.getAllNeighbors(type=None):
            for timer in node.getTimers():
                timer.resume()
            for edge in node.getEdges():
                for timer in edge.getTimers():
                    timer.resume()

    def copy(self, configuration=None):
        """
        Copy the graph containing all hosts and networks that are in a given configuration.
        If configuration is None a full copy will be returned.

        :param configuration: All hosts and networks must be contained in this configuration
        :type configuration: str
        """
        hosts = [h for h in self.getAllNeighbors(type=Host) if not configuration or configuration in h.getConfigNames()]
        l2networks = [n for n in self.getAllNeighbors(type=Layer2Network) if not configuration or configuration in n.getConfigNames()]
        interfaces = list(itertools.chain(*[h.getInterfaces() for h in hosts])) # Get all interfaces of hosts in this configuration
        l3addresses = list(itertools.chain(*[i.getAddresses() for i in interfaces])) # Get all l3addresses of those interfaces
        l3networks = [a.getNetwork() for a in l3addresses] # Get the network of all addresses
        name = configuration if configuration else self.getID()

        return Graph(name, allHosts=set(hosts), allL2Networks=set(l2networks), allL3Networks=set(l3networks))

    #Getter/Setter
    def getID(self):
        return self.id

    def getGlobalID(self):
        return self.getID()

    def getHosts(self):
        return frozenset(self.getAllNeighbors(Host))

    def getL2Networks(self):
        return frozenset(self.getAllNeighbors(Layer2Network))

    def getL3Networks(self):
        return frozenset(self.getAllNeighbors(Layer3Network))

    def getLocations(self):
        return frozenset(self.getAllNeighbors(Location))

    def getEdge(self, first, second):
        """
        Get the Edge object between two objects.

        Arguments:
            first -- First hosts that is incident to the edge.
            second -- Second host that is incident to the edge.

        Return:
            Edge if existing or None
        """
        edges = [e for e in first.getEdges() if e.getOther(first) is second]
        if len(edges) == 0:
            return None
        return edges[0]


    def getOrCreateHost(self, id, collectorName, timeout, location=None, template=None):
        """
        Get the host with the given id or create a new one.

        :param id: Identifier of the host
        :type id: str

        :param collectorName: Name of the collector requesting this host
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param location: Location containing this host
        :type location: insalata.model.Location.Location

        :param template: Template the host is build on
        :type template: str
        """
        self.__locks[Host].acquire()
        hosts = [h for h in self.getAllNeighbors(Host) if h.getGlobalID() == id]

        if len(hosts) > 0:
            host = list(hosts)[0]
            host.setLocation(location, collectorName, timeout)
            host.setTemplate(template, collectorName, timeout)
            host.verify(collectorName, timeout)
        else:
            host = Host(id, collectorName=collectorName, timeout=timeout, location=location, template=template)
            Edge(self, host)

            host.getOnChangeEvent().add(partial(self.objectChanged))
            host.getOnDeleteEvent().add(partial(self.objectDeleted))
            valuesDict = {
                "id" : id
            }
            if location:
                valuesDict["location"] = location.getID()
            if template:
                valuesDict["template"] = template.getID()
            self.getObjectNewEvent().trigger(self, { "objectType" : "Host", "values" : valuesDict })

        self.__locks[Host].release()
        return host

    def getOrCreateLayer2Network(self, id, collectorName, timeout, location=None):
        """
        Get the Layer2Network with the given id or create a new one.

        :param id: Identifier of the network
        :type id: str

        :param collectorName: Name of the collector requesting this network
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param location: The locatin containing this network
        :type location: insalata.model.Location.Location
        """
        self.__locks[Layer2Network].acquire()
        networks = [n for n in self.getAllNeighbors(Layer2Network) if n.getGlobalID() == id]

        if len(networks) > 0:
            network = list(networks)[0]
            network.setLocation(location, collectorName, timeout)
            network.verify(collectorName, timeout)
        else:
            network = Layer2Network(id, collectorName=collectorName, timeout=timeout, location=location)
            Edge(self, network)

            network.getOnChangeEvent().add(partial(self.objectChanged))
            network.getOnDeleteEvent().add(partial(self.objectDeleted))
            valuesDict = {
                "id" : id
            }
            if location:
                valuesDict["location"] = location.getID()
            self.getObjectNewEvent().trigger(self, { "objectType" : "Layer2Network", "values" : valuesDict })

        self.__locks[Layer2Network].release()
        return network

    def getOrCreateInterface(self, mac, collectorName, timeout, network=None):
        """
        Get the interface with the given MAC address or create a new one if it is not existing

        :param mac: MAC address of the interface
        :type mac: str

        :param collectorName: Name of the collector requesting this interface
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param network: Network this interface is conntected to
        :type network: insalata.model.Layer2Network.Layer2Network
        """
        self.__locks[Interface].acquire()
        interfaces = [i for i in self.getAllNeighbors(Interface) if i.getMAC() == mac]

        if len(interfaces) > 0:
            interface = list(interfaces)[0]
            interface.setNetwork(network, collectorName, timeout)
            interface.verify(collectorName, timeout)
        else:
            interface = Interface(mac, collectorName=collectorName, timeout=timeout, network=network)
            Edge(self, interface)

            interface.getOnChangeEvent().add(self.objectChanged)
            interface.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "mac" : mac
            }
            if network:
                valuesDict["network"] = network.getID()
            self.getObjectNewEvent().trigger(self, { "objectType" : "Interface" , "values" : valuesDict })

        self.__locks[Interface].release()
        return interface

    def getOrCreateLayer3Network(self, id, collectorName, timeout, address, netmask):
        """
        Get the Layer3Network with the given identifier or create a new one if it is not existing.

        :param id: Identifier of the network
        :type id: str

        :param collectorName: Name of the collector requesting this network
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param address: Address of this network
        :type address: str

        :param netmask: Netmask of the network
        :type netmask: str
        """
        self.__locks[Layer3Network].acquire()
        networks = [n for n in self.getAllNeighbors(Layer3Network) if n.getGlobalID() == id]

        if len(networks) > 0:
            network = list(networks)[0]
            network.setAddress(address, collectorName, timeout)
            network.setNetmask(netmask, collectorName, timeout)
            network.verify(collectorName, timeout)
        else:
            network = Layer3Network(id, address, netmask, collectorName=collectorName, timeout=timeout)
            Edge(self, network)

            network.getOnChangeEvent().add(self.objectChanged)
            network.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "id" : id,
                "address" : address,
                "netmask" : netmask
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "Layer3Network", "values" : valuesDict })

        self.__locks[Layer3Network].release()
        return network

    def getOrCreateLayer3Address(self, address, collectorName, timeout, netmask=None, gateway=None):
        """
        Get the Layer3Address with the given address or create it if it does not exist.

        :param address: Address of this Layer3Address
        :type address: str

        :param collectorName: Name of the collector requesting this address
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param netmask: Netmask of this address
        :type netmask: str

        :param gateway: Gateway of this addess
        :type gateway: str
        """
        self.__locks[Layer3Address].acquire()
        addresses = [a for a in self.getAllNeighbors(Layer3Address) if a.getID() == address]

        if len(addresses) > 0:
            addressEl = list(addresses)[0]
            addressEl.setGateway(gateway, collectorName, timeout)
            addressEl.setNetmask(netmask, collectorName, timeout)
            addressEl.verify(collectorName, timeout)
        else:
            addressEl = Layer3Address(address, netmask=netmask, gateway=gateway, collectorName=collectorName, timeout=timeout)
            Edge(self, addressEl)

            addressEl.getOnChangeEvent().add(self.objectChanged)
            addressEl.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "address" : address,
                "gateway" : gateway,
                "netmask" : netmask
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "Layer3Address", "values" : valuesDict })

        self.__locks[Layer3Address].release()
        return addressEl

    def getOrCreateService(self, port, protocol, collectorName, timeout, type, address):
        """
        Get the Service with the given port on the given address or create it if it does not exist.

        :param port: Port of this service
        :type port: int

        :param protocol: Protocol this service is using
        :type protocol: str

        :param collectorName: Name of the collector requesting this service
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param type: Type/Name of the service
        :type netmask: str

        :param address: Address this service is deployed on
        :type gateway: insalata.model.Layer3Address.Layer3Address
        """
        self.__locks[Service].acquire()
        services = [s for s in address.getAllNeighbors(Service) if s.getPort() == port and s.getProtocol() == protocol]

        if len(services) > 0:
            service = list(services)[0]
            service.setType(type, collectorName, timeout)
            service.verify(collectorName, timeout)
        else:
            service = Service(port, protocol,  type, collectorName=collectorName, timeout=timeout, address=address)
            Edge(self, service)

            service.getOnChangeEvent().add(self.objectChanged)
            service.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "port" : port,
                "protocol" : protocol,
                "type" : type,
                "address" : address.getID()
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "Service", "values" : valuesDict })

        self.__locks[Service].release()
        return service

    def getOrCreateDhcpService(self, collectorName, timeout, address):
        """
        Get the DhcpService on the given address or create a new one if necessary.

        :param collectorName: Name of the collector requesting this service
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param address: Address this service is deployed on
        :type gateway: insalata.model.Layer3Address.Layer3Address
        """
        self.__locks[DhcpService].acquire()
        services = [s for s in address.getAllNeighbors(DhcpService) if s.getType() == "dhcp"]

        if len(services) > 0:
            service = list(services)[0]
            service.setAddress(address, collectorName, timeout)
            service.verify(collectorName, timeout)
        else:
            service = DhcpService(collectorName=collectorName, timeout=timeout, address=address)
            Edge(self, service)

            service.getOnChangeEvent().add(self.objectChanged)
            service.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "address" : address.getID()
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "DhcpService", "values" : valuesDict })

        self.__locks[DhcpService].release()
        return service

    def getOrCreateDnsService(self, collectorName, timeout, address):
        """
        Get the DnsService on the given address or create a new one if necessary.

        :param collectorName: Name of the collector requesting this service
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param address: Address this service is deployed on
        :type gateway: insalata.model.Layer3Address.Layer3Address
        """
        self.__locks[DnsService].acquire()
        services = [s for s in address.getAllNeighbors(DnsService) if s.getType() == "dns"]

        if len(services) > 0:
            service = list(services)[0]
            service.setAddress(address, collectorName, timeout)
            service.verify(collectorName, timeout)
        else:
            service = DnsService(collectorName=collectorName, timeout=timeout, address=address)
            Edge(self, service)

            service.getOnChangeEvent().add(self.objectChanged)
            service.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "address" : address.getID()
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "DnsService", "values" : valuesDict })

        self.__locks[DnsService].release()
        return service


    def getOrCreateDisk(self, name, collectorName, timeout, host, size=None):
        """
        Get the host disk with the given name if existing or create a new one.

        :param name: Name of the disk on the host
        :type name: str

        :param collectorName: Name of the collector requesting this address
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param host: Host that contains the disk
        :type host: insalata.model.Host.Host

        :param size: Size of the disk
        :type size: int
        """
        self.__locks[Disk].acquire()
        disk = [d for d in host.getAllNeighbors(Disk) if d.getGlobalID() == name]

        if len(disk) > 0:
            disk = list(disk)[0]
            disk.setSize(size, collectorName, timeout)
            disk.verify(collectorName, timeout)
        else:
            disk = Disk(name, size=None, collectorName=collectorName, timeout=timeout)
            Edge(self, disk)

            disk.getOnChangeEvent().add(self.objectChanged)
            disk.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "name" : name,
                "host" : host.getID(),
                "size" : size
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "Disk", "values" : valuesDict })

        self.__locks[Disk].release()
        return disk

    def getOrCreateLocation(self, id, collectorName, timeout):
        """
        Get the location with the given name if existing or create a new one.

        :param id: Name of the location
        :type id: str

        :param collectorName: Name of the collector requesting this address
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int
        """
        self.__locks[Location].acquire()
        location = [l for l in self.getAllNeighbors(Location) if l.getGlobalID().lower() == id.lower()]

        if len(location) > 0:
            location = list(location)[0]
            location.verify(collectorName, timeout)
        else:
            location = Location(id, collectorName=collectorName, timeout=timeout)
            Edge(self, location)

            location.getOnChangeEvent().add(self.objectChanged)
            location.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "id" : id
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "Location", "values" : valuesDict })

        self.__locks[Location].release()
        return location


    def getOrCreateRoute(self, collectorName, timeout, host, dest, genmask, gateway, interface=None):
        """
        Get the route with the given parametes on the host if existing or create a new one.

        :param collectorName: Name of the collector requesting this address
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param host: Host that shall contain the route
        :type host: insalata.model.Host.Host

        :param dest: Destination address of this route
        :type dest: str

        :param genmask: Genmask used by this route
        :type genmask: str

        :param gateway: Gateway used by this route
        :type gateway: str

        :param interface: Interface this route uses for forwarding
        :type interface: insalata.model.Interface.Interface
        """
        self.__locks[Route].acquire()
        routes = [r for r in host.getAllNeighbors(Route) if r.getGateway() == gateway 
            and r.getDestination() == dest
            and r.getGenmask() == genmask]
        if len(routes) > 0:
            route = routes[0]
            route.setInterface(interface, collectorName, timeout)
            route.verify(collectorName, timeout)
        else:
            route = Route(dest, genmask, gateway, interface=interface, collectorName=collectorName, timeout=timeout)
            Edge(self, route)

            route.getOnChangeEvent().add(self.objectChanged)
            route.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "host" : host.getID(),
                "dest" : dest,
                "genmask" : genmask,
                "gateway" : gateway
            }
            if interface:
                valuesDict["interface"] = interface.getID()
            self.getObjectNewEvent().trigger(self, { "objectType" : "Route", "values" : valuesDict })

        self.__locks[Route].release()
        return route

    def getOrCreateFirewallRule(self, collectorName, timeout, host, chain, action, protocol, srcnet=None, destnet=None, srcports=None, destports=None, inInterface=None, outInterface=None):
        """
        Get the rule with the given parametes on the host if existing or create a new one.

        :param collectorName: Name of the collector requesting this address
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param host: Host that shall contain the rule
        :type host: insalata.model.Host.Host

        :param chain: The name of the chain this rule belongs to.
        :type chain: str

        :param action: The action (ACCEPT or DROP) for this rule.
        :type action: str

        :param protocol: Protocol for this rule
        :type protocol: str

        :param srcnet: Source network of this rule
        :type srcnet: str

        :param destnet: Source network of this rule
        :type destnet: str

        :param srcports: Source ports this rule uses
        :type srcports: list

        :param destports: Destination ports this rule uses
        :type destports: list

        :param inInterface: Interface the packet came from
        :type inInterface: insalata.model.Interface.Interface

        :param outInterface: Interface the packet leafes from
        :type outInterface: insalata.model.Interface.Interface
        """
        self.__locks[FirewallRule].acquire()
        rules = [r for r in host.getAllNeighbors(FirewallRule) if r.getChain() == chain
            and r.getAction() == action 
            and r.getProtocol() == protocol 
            and r.getSrcNet() == srcnet
            and r.getDestNet() == destnet
            and r.getSrcPorts() == srcports
            and r.getDestPorts() == destports
            and r.getInInterface() == inInterface
            and r.getOutInterface() == outInterface]
        if len(rules) > 0:
            rule = rules[0]
            rule.verify(collectorName, timeout)
        else:
            rule = FirewallRule(chain, action, protocol, srcnet, destnet, srcports, destports, inInterface, outInterface, collectorName, timeout)
            Edge(self, rule)

            rule.getOnChangeEvent().add(self.objectChanged)
            rule.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "host" : host.getID(),
                "chain" : chain,
                "action" : action,
                "protocol" : protocol
            }
            if srcnet:
                valuesDict["srcNetwork"] = srcnet
            if destnet:
                valuesDict["destNetwork"] = destnet
            if srcports and len(srcports) > 0:
                valuesDict["srcPorts"] = str(srcports[0]) if len(srcports) == 1 else str(srcports[0]) + ":" + str(srcports[-1])
            if srcports and len(destports) > 0:
                valuesDict["destPorts"] = str(destports[0]) if len(destports) == 1 else str(destports[0]) + ":" + str(destports[-1])
            if inInterface:
                valuesDict["inInterface"] = inInterface.getID()
            if outInterface:
                valuesDict["outInterface"] = outInterface.getID()
            self.getObjectNewEvent().trigger(self, { "objectType" : "FirewallRule", "values" : valuesDict })

        self.__locks[FirewallRule].release()
        return rule

    def getOrCreateFirewallRaw(self, collectorName, timeout, host, firewall, data=None):
        """
        Get the rule with the given parametes on the host if existing or create a new one.

        :param collectorName: Name of the collector requesting this address
        :type collectorName: str

        :param timeout: Timeout of the collector
        :type timeout: int

        :param host: Host that shall contain the rule
        :type host: insalata.model.Host.Host

        :param chain: The name of the chain this rule belongs to.
        :type chain: str

        :param firewall: The productname of the firewall, e.g. "iptables"
        :type firewall: str

        :param data: Raw firewall data of the given firewall type
        :type data: str
        """
        self.__locks[FirewallRaw].acquire()
        raws = [r for r in host.getAllNeighbors(FirewallRaw) if r.getFirewall() == firewall]

        if len(raws) == 0:
            raw = FirewallRaw(firewall, data, collectorName, timeout)
            Edge(self, raw)

            raw.getOnChangeEvent().add(self.objectChanged)
            raw.getOnDeleteEvent().add(self.objectDeleted)
            valuesDict = {
                "host" : host.getID(),
                "firewall" : firewall,
                "data" : data
            }
            self.getObjectNewEvent().trigger(self, { "objectType" : "FirewallRaw", "values" : valuesDict })

        else:
            raw = raws[0]
            raw.verify(collectorName, timeout)

        self.__locks[FirewallRaw].release()
        return raw

    def objectChanged(self, sender, args):
        args["object"] = sender.getID()
        args["objectType"] = sender.__class__.__name__
        self.getObjectChangedEvent().trigger(self, args)

    def objectDeleted(self, sender, args):
        sender.getOnChangeEvent().remove(partial(self.objectChanged))
        sender.getOnDeleteEvent().remove(partial(self.objectDeleted))
        args["objectType"] = sender.__class__.__name__
        args["object"] = sender.getID()
        self.getObjectDeletedEvent().trigger(self, args)


from insalata.model.Host import Host
from insalata.model.Route import Route
from insalata.model.FirewallRule import FirewallRule
from insalata.model.FirewallRaw import FirewallRaw
from insalata.model.Layer3Network import Layer3Network
from insalata.model.Layer2Network import Layer2Network
from insalata.model.Disk import Disk
from insalata.model.Interface import Interface
from insalata.model.DhcpService import DhcpService
from insalata.model.DnsService import DnsService
from insalata.model.Service import Service
from insalata.model.Layer3Address import Layer3Address
from insalata.model.Location import Location
from insalata.model.Edge import Edge

from insalata.planning import planner
from insalata.helper import diff
from insalata.helper import ipAddressHelper