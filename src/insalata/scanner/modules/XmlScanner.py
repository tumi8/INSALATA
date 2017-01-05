from lxml import etree
from insalata.model.Location import Location
from insalata.model.Layer2Network import Layer2Network
from insalata.model.Layer3Network import Layer3Network
from insalata.model.Interface import Interface


def scan(graph, connectionInfo, logger, thread):
    """
    Load the network topology given in an XML file into the graph.
    Timer is -1 => Objects will not be deleted.
    Therefore, the infrastructure in the XML file is laoded permanently until the XML is changed.

    The module is able to detect changes in the XML file. Therefore, it is possible to modify the 
    loaded information at runtime.

    Necessary values in the configuration file of this collector module:
        - file  Path to the XML file the collector module shall parse
    
    :param graph: Data interface object for this collector module
    :type graph: insalata.model.Graph.Graph

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: logging:Logger

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """

    logger.info("Reading xml file '{0}' into internal graph.".format(connectionInfo['file']))

    timeout = -1
    name = connectionInfo['name']

    configXml = etree.parse(connectionInfo['file'])

    readElements = set()
    readLocations(graph, configXml.find("locations"), logger, name, timeout, readElements)
    readL2Networks(graph, configXml.find("layer2networks"), logger, name, timeout, readElements)
    readL3Networks(graph, configXml.find("layer3networks"), logger, name, timeout, readElements)
    readHosts(graph, configXml.xpath(".//host[not(@control)]"), logger, name, timeout, readElements)


    for element in graph.getAllNeighbors():
        inList = False
        for el in readElements:
            if el == element:
                inList = True
        if not inList: #Delete verification for these as they do not appear in the Xml
            element.removeVerification(name)


def readHosts(graph, hostsXml, logger, name, timeout, readElements):
    """
    Load hosts of the xml file into the graph.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param hostsXml: Part of the parsed XML containing the hosts.
    :type hostsXml: list

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    logger.debug("Reading all hosts given in XML")
    if not hostsXml:
        return
    for hostXml in hostsXml:
        if "location" in hostXml.attrib:
            location = graph.getOrCreateLocation(hostXml.attrib["location"], name, timeout)
        else: 
            location = graph.getOrCreateLocation(hostXml.attrib["physical"])
        readElements.add(location)

        template = [t for t in location.getTemplates() if t.getID() == hostXml.attrib["template"]]

        if len(template) > 0:
            template = template[0]  #No template shouldn't be possible if xml passed the preprocessor
        host = graph.getOrCreateHost(hostXml.attrib["id"], name, timeout, location, template)
        readElements.add(host)
        logger.debug("Found host: {0}.".format(hostXml.attrib["id"]))

        if "cpus" in hostXml.attrib:
            host.setCPUs(int(hostXml.attrib["cpus"]))
        if ("memoryMin" in hostXml.attrib) and ("memoryMax" in hostXml.attrib): 
            host.setMemory(int(hostXml.attrib["memoryMin"]), int(hostXml.attrib["memoryMax"]))
        if "powerState" in hostXml.attrib:
            host.setPowerState(hostXml.attrib["powerState"])

        #interfaces, routing, firewall rules and disks added with edges
        if hostXml.find("interfaces") is not None:
            readInterfaces(graph, hostXml.find("interfaces"), host, logger, name, timeout, readElements)
        if hostXml.find("routes") is not None:
            readRoutes(graph, hostXml.find("routes"), host, logger, name, timeout, readElements)
        if hostXml.find("disks") is not None:
            readDisks(graph, hostXml.find("disks"), host, logger, name, timeout, readElements)
        if hostXml.find(".//firewallRules") is not None:
            readFirewallRules(graph, hostXml.find(".//firewallRules"), host, logger, name, timeout, readElements)

        #find firewall raw data
        if hostXml.find('.//raw') is not None:
            rawXml = hostXml.find('.//raw')
            if rawXml is not None:
                raw = graph.getOrCreateFirewallRaw(name, timeout, host, rawXml.attrib["firewall"], rawXml.text)
                host.setFirewallRaw(raw)
                readElements.add(raw)

def readInterfaces(graph, interfacesXml, host, logger, name, timeout, readElements):
    """
    Load all interfaces of a host. The interfaces will be added to the host.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param interfacesXml: Part of the parsed XML containing the interfaces of the current host.
    :type interfacesXml: list

    :param host: The host that contains the read interfaces
    :type host: insalata.model.Host.Host

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    if interfacesXml:
        logger.debug("Reading interfaces from XML.")
    if not interfacesXml:
        return
    for ifaceXml in interfacesXml.findall("interface"):
        if not "network" in ifaceXml.attrib:
            logger.warning("No network attribute found for interface '{0}'.".format(ifaceXml.attrib["mac"]))
            continue

        network = [n for n in graph.getAllNeighbors(Layer2Network) if n.getID() == ifaceXml.attrib["network"]]
        if len(network) == 0:
            logger.warning("No suitable network found for interface '{0}'.".format(ifaceXml.attrib["mac"]))
            continue
        else:
            network = network[0]

        interface = graph.getOrCreateInterface(ifaceXml.attrib["mac"], name, timeout, network=network)
        readElements.add(interface)
        logger.debug("Found Interface with mac: {0}.".format(interface.getID()))
        if "rate" in ifaceXml.attrib:
            interface.setRate(ifaceXml.attrib["rate"])
        if "mtu" in ifaceXml.attrib:
            interface.setMtu(ifaceXml.attrib["mtu"])

        host.addInterface(interface, name, timeout)
        readLayer3Addresses(graph, ifaceXml.findall("layer3address"), interface, logger, name, timeout, readElements)


def readLayer3Addresses(graph, layer3AddressesXml, interface, logger, name, timeout, readElements):
    """
    Load all Layer3Addresses of a interface. The addresses will be added to the interface automatically.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param layer3AddressesXml: Part of the parsed XML containing the Layer3Addresses of the interface.
    :type layer3AddressesXml: list

    :param interface: The interface containing the addresses
    :type host: insalata.model.Interface.Interface

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    if layer3AddressesXml:
        logger.debug("Read all Layer3Addresses of interface {0} in XML.".format(interface.getID()))
    if not layer3AddressesXml:
        return
    for addressXml in layer3AddressesXml:
        network = None
        if "network" in addressXml.attrib: 
            network = [n for n in graph.getAllNeighbors(Layer3Network) if n.getID() == addressXml.attrib["network"]]
            if len(network) == 0:
                logger.warning("No suitable network found for {0}.".format(addressXml.attrib["network"]))
                network = None
                netmask = None
            else:
                network = network[0]
                netmask = network.getNetmask() if not "netmask" in addressXml.attrib else addressXml.attrib["netmask"]

            gateway = None if not "gateway" in addressXml.attrib else addressXml.attrib["gateway"]

            address = graph.getOrCreateLayer3Address(addressXml.attrib["address"], name, timeout,  netmask, gateway)
            readElements.add(address)

            if "static" in addressXml.attrib:
                address.setStatic(addressXml.attrib["static"] == "True")
            else:
                address.setStatic(True)

            if network:
                address.setNetwork(network)

            interface.addAddress(address, name, timeout)

            #get services
            if addressXml.find("services") is not None:
                readServices(graph, addressXml.find("services"), address, logger, name, timeout, readElements)


def readServices(graph, servicesXml, address, logger, name, timeout, readElements):
    """
    Load all services of a Layer3Address. The services willbe added automatically.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param servicesXml: Part of the parsed XML containing the services of this address.
    :type hostsXml: list

    :param address: The Layer3Address the services are provided on
    :type address: insalata.model.Layer3Address.Layer3Address

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    if not servicesXml:
        return
    if servicesXml:
        logger.debug("Reading Services from XML for address: {0}.".format(address.getID()))

        for serviceXml in servicesXml:
            #special dhcp service
            if serviceXml.tag == "dhcp":
                service = graph.getOrCreateDhcpService(name, timeout, address)
                if "lease" in serviceXml.attrib:
                    service.setLease(serviceXml.attrib["lease"])
                if ("from" or "to") in serviceXml.attrib:
                    service.setStartEnd(serviceXml.attrib["from"], serviceXml.attrib["to"])
                if ("announcedGateway") in serviceXml.attrib:
                    service.setAnnouncedGateway(serviceXml.attrib["announcedGateway"])

            #special dns service
            elif serviceXml.tag == "dns":
                service = graph.getOrCreateDnsService(name, timeout, address)
                if "domain" in serviceXml.attrib:
                    service.setDomain(serviceXml.attrib["domain"])


            #add more special services here, e.g. http
            #generic unknown services
            else:
                service = graph.getOrCreateService(serviceXml.attrib["port"], serviceXml.attrib["protocol"], name, timeout, serviceXml.attrib["type"], address)
                if "type" in serviceXml.attrib:
                    service.setName(serviceXml.attrib["type"])
                if "product" in serviceXml.attrib:
                    service.setProduct(serviceXml.attrib["product"])
                if "version" in serviceXml.attrib:
                    service.setVersion(serviceXml.attrib["version"])

            readElements.add(service)
            address.addService(service, name, timeout)


def readRoutes(graph, routingXml, host, logger, name, timeout, readElements):
    """
    Load all routes of a host. The routes will be added to the host automatically.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param routingXml: Part of the parsed XML containing the routes.
    :type routingXml: list

    :param host: The host that contains the read routes.
    :type host: insalata.model.Host.Host

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    if not routingXml:
        return
    if routingXml:
        logger.debug("Reading all Routes from XML for host {0}.".format(host.getID()))

        for routeXml in routingXml:
            interface = None
            if "interface" in routeXml.attrib:
                interface = [i for i in graph.getAllNeighbors(Interface) if i.getID() == routeXml.attrib["interface"]]
                if len(interface) == 0:
                    logger.debug("No interface found found for route. Interface: {0}.".format(routeXml.attrib["interface"]))
                else:
                    interface = interface[0]

            route = graph.getOrCreateRoute(name, timeout, host, routeXml.attrib["destination"], routeXml.attrib["genmask"], routeXml.attrib["gateway"], interface)
            host.addRoute(route, name, timeout)
            readElements.add(route)


def readFirewallRules(graph, rulesXml, host, logger, name, timeout, readElements):
    """
    Load all firewall rules of a host. The rules will be added to the host automatically.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param rulesXml: Part of the parsed XML containing the firewall rules.
    :type rulesXml: list

    :param host: The host that contains the read firewall rules.
    :type host: insalata.model.Host.Host

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    logger.debug("Reading all firewall rules from XML for host {0}.".format(host.getID()))
    if not rulesXml:
        return
    for ruleXml in rulesXml:
        interface = [i for i in graph.getAllNeighbors(Interface) if "inInterface" in ruleXml.attrib and i.getID() == ruleXml.attrib["inInterface"]]
        inInterface = interface[0] if len(interface) > 0 else None

    if rulesXml:
        logger.debug("Reading all firewall rules from XML for host {0}.".format(host.getID()))
        for ruleXml in rulesXml:
            interface = [i for i in graph.getAllNeighbors(Interface) if "inInterface" in ruleXml.attrib and i.getID() == ruleXml.attrib["inInterface"]]
            inInterface = interface[0] if len(interface) > 0 else None

            interface = [i for i in graph.getAllNeighbors(Interface) if "outInterface" in ruleXml.attrib and i.getID() == ruleXml.attrib["outInterface"]]
            outInterface = interface[0] if len(interface) > 0 else None

            srcnet = destnet = srcports = destports = protocol = None
            if "chain" in ruleXml.attrib:
                chain = ruleXml.attrib["chain"]
            if "action" in ruleXml.attrib:
                action = ruleXml.attrib["action"]
            if "srcnet" in ruleXml.attrib:
                srcnet = ruleXml.attrib["srcnet"]
            if "destnet" in ruleXml.attrib:
                destnet = ruleXml.attrib["destnet"]
            if "srcports" in ruleXml.attrib:
                srcports = ruleXml.attrib["srcports"]
            if "destports" in ruleXml.attrib:
                destports = ruleXml.attrib["destports"]
            if "protocol" in ruleXml.attrib:
                protocol = ruleXml.attrib["protocol"]

            rule = graph.getOrCreateFirewallRule(name, timeout, host, chain, action, protocol, srcnet, destnet, srcports, destports, inInterface, outInterface)
            host.addFirewallRule(rule, name, timeout)
            readElements.add(rule)


def readDisks(graph, disksXml, host, logger, name, timeout, readElements):
    """
    Load all disks of a host. The disks will be added to the host.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param disksXml: Part of the parsed XML containing the disks of the current host.
    :type disksXml: list

    :param host: The host that contains the read interfaces.
    :type host: insalata.model.Host.Host

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    logger.debug("Read all disks on host {0}.".format(host.getID()))
    if not disksXml:
        return
    for diskXml in disksXml:
        logger.debug("Found disk {0} for host {1}.".format(diskXml.attrib["id"], host.getID()))
        disk = graph.getOrCreateDisk(diskXml.attrib["id"], name, timeout, host)
        if "size" in diskXml.attrib:
            disk.setSize(int(diskXml.attrib["size"]))
        logger.debug("Adding disk '{0}' to host '{1}'".format(disk.getID(), host.getID()))
        host.addDisk(disk, name, timeout)
        readElements.add(disk)

    if disksXml:
        logger.debug("Read all disks on host {0}.".format(host.getID()))
        for diskXml in disksXml:
            logger.debug("Found disk {0} for host {1}.".format(diskXml.attrib["id"], host.getID()))
            disk = graph.getOrCreateDisk(diskXml.attrib["id"], name, timeout, host)
            if "size" in diskXml.attrib:
                disk.setSize(int(diskXml.attrib["size"]))
            logger.debug("Adding disk '{0}' to host '{1}'".format(disk.getID(), host.getID()))
            host.addDisk(disk, name, timeout)
            readElements.add(disk)


def readL2Networks(graph, l2networksXml, logger, name, timeout, readElements):
    """
    Load all Layer2Networks given in the XML.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param l2networksXml: Part of the parsed XML containing the networks.
    :type l2networksXml: list

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    if l2networksXml:
        logger.debug("Reading Layer2Networks from XML.")
    if not l2networksXml:
        return

    for netXml in l2networksXml.findall("layer2network"):
        if "location" in netXml.attrib:
            location = graph.getOrCreateLocation(netXml.attrib["location"], name, timeout)
        else:
            location = graph.getOrCreateLocation("physical", name, timeout)

        readElements.add(location)

        readElements.add(graph.getOrCreateLayer2Network(netXml.attrib["id"], name, timeout, location))
        logger.debug("Found Layer2Network {0} in location {1}.".format(netXml.attrib["id"], location.getID()))


def readL3Networks(graph, l3networksXml, logger, name, timeout, readElements):
    """
    Load all Layer3Networks given in the XML.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param l3networksXml: Part of the parsed XML containing the networks.
    :type l3networksXml: list

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    if l3networksXml is None:
        return
    if l3networksXml:
        logger.debug("Reading Layer3Networks from XML.")

        for netXml in l3networksXml.findall("layer3network"):
            readElements.add(graph.getOrCreateLayer3Network(netXml.attrib["id"], name, timeout, netXml.attrib["address"], netXml.attrib["netmask"]))
            logger.debug("Found Layer3Network: {0}.".format(netXml.attrib["id"]))


def readLocations(graph, locationsXml, logger, name, timeout, readElements):
    """
    Load all Locations given in the XML.
    
    :param graph: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param locationsXml: Part of the parsed XML containing the locations.
    :type locationsXml: list

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param name: Name this collector module uses for verification
    :type name: str

    :param timeout: Timeout of this collector module
    :type timeout: int

    :param readElements: Set containing every read element from the XML -> Allows to delete not longer existing ones
    :type readElements: set
    """
    if not locationsXml:
        return
    if locationsXml:
        logger.debug("Reading Locations from XML.")

        for locationXml in locationsXml.findall("location"):
            location = graph.getOrCreateLocation(locationXml.attrib["id"], name, timeout)
            logger.debug("Found location: {0}.".format(location.getID()))
            readElements.add(location)
