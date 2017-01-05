from insalata import RpcConnection
from insalata.model.Interface import Interface
from insalata.model.Host import Host
from insalata.model.Layer2Network import Layer2Network

def scan(graph, connectionInfo, logger, thread):
    """
    Method reads interface information from a Xen server.

    Necessary values in the configuration file of this collector module:
        - timeout   Timeout this collector module shall use (Integer)
        - xenuri    The URI opf the Xen server
        - xenuser   The username we use to connect to the Management API of the Xen server
        - xenpw     Password used for the connection
    
    :param graph: Data interface object for this collector module
    :type graph: insalata.model.Graph.Graph

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: logging:Logger

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """
    logger.info("Reading interfaces on server: {0}".format(connectionInfo['xenuri']))

    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    rpcConn = None
    xen = None
    session = None
    try:
        rpcConn = RpcConnection.RpcConnection(connectionInfo['xenuri'], connectionInfo['xenuser'], connectionInfo['xenpw'])
        xen, session = rpcConn.getConnectionSession()
    except:
        logger.error("Connection to Xen Server {0} not possible.".format(connectionInfo['xenuri']))
        return

    answer = xen.VM.get_all_records(session)
    if answer['Status'] == 'Failure':
        logger.error("Interface scan on Xen server {0} failed. Server sent failure while reading all VMs.".format(connectionInfo['xenuri']))
        return
    hostRecords = answer['Value']

    answer = xen.VIF.get_all_records(session)
    if answer['Status'] == 'Failure':
        logger.error("Interface scan on Xen server {0} failed. Server sent failure while reading all VIfs.".format(connectionInfo['xenuri']))
        return
    VIFRecords = answer['Value']

    answer = xen.network.get_all_records(session)
    if answer['Status'] == 'Failure':
        logger.error("Interface scan on Xen server {0} failed. Server sent failure while reading all networks.".format(connectionInfo['xenuri']))
        return
    networkRecords = answer['Value']


    #Update interfaces themselves
    interfacesOnServer = set([VIFRecords[record]['MAC'] for record in VIFRecords if networkRecords[VIFRecords[record]['network']]['name_label'] != "controll-network"])
    # Interfaces to the controll-network shall not appear in the graph
    stillExistingInterfaces = set()
    deletedInterfaces = set()
    currentInterfaces = graph.getAllNeighbors(Interface)
    for interface in currentInterfaces:
        if interface.getMAC() in interfacesOnServer:
            stillExistingInterfaces.add(interface)
            interface.verify(name, timeout)
        else:
            deletedInterfaces.add(interface)
        interfacesOnServer.remove(interface.getMAC()) #Determine which interfaces are new

    for interface in deletedInterfaces:
        interface.removeVerification(name)

    for mac in interfacesOnServer:
        stillExistingInterfaces.add(graph.getOrCreateInterface(mac, name, timeout))


    #Assign interfaces to hosts
    for host in graph.getAllNeighbors(type=Host):
        logger.debug("Starting interface scan for host: {0}".format(host.getID()))
        answer = xen.VM.get_by_name_label(session, host.getGlobalID())
        if answer['Status'] == 'Failure' or len(answer['Value']) == 0:
            logger.error("Interface scan on Xen server {0} failed. Server sent failure while getting host record for: {1}".format(connectionInfo['xenuri'], host.getGlobalID()))
            continue
        hostRecord = answer['Value'][0]

        currentHostInterfaces = host.getAllNeighbors(type=Interface)
        hostInterfacesOnServer = [VIFRecords[record]['MAC'] for record in hostRecords[hostRecord]['VIFs'] if networkRecords[VIFRecords[record]['network']]['name_label'] != "controll-network"]
        stillExistingHostInterfaces = hostInterfacesOnServer
        for interface in currentHostInterfaces:
            if not interface.getMAC() in hostInterfacesOnServer:
                for edge in [e for e in host.getEdges() if e.getOther(host) == interface]:
                    edge.removeVerification(name)

        for mac in stillExistingHostInterfaces:
            interface =  graph.getOrCreateInterface(mac, name, timeout)
            logger.debug("Adding interface {0} to host {1}.".format(interface.getID(), host.getID()))
            host.addInterface(interface, name, timeout)
            record = [record for record in VIFRecords if VIFRecords[record]['MAC'] == mac]
            if len(record) > 0: # Get the record on xen for this interface
                record = record[0]
                if VIFRecords[record]['qos_algorithm_type'] == "ratelimit" and "kbps" in VIFRecords[record]['qos_algorithm_params']:
                    interface.setRate(VIFRecords[record]['qos_algorithm_params']['kbps'])
                interface.setMtu(VIFRecords[record]['MTU'])


        for interface in stillExistingHostInterfaces:
            edge = graph.getEdge(host, interface)
            if edge is not None:
                edge.verify(name, timeout)


    #Assign networks to interfaces
    currentNetworks = graph.getAllNeighbors(type=Layer2Network)
    for interface in stillExistingInterfaces:
        intRec = getInterfaceRecord(VIFRecords, interface.getMAC())
        if intRec is None:
            continue
        networkNameOnServer = networkRecords[VIFRecords[intRec]['network']]['name_label']
        network = getNetwork(currentNetworks, networkNameOnServer)
        if network is not None:
            interface.setNetwork(network, name, timeout)

    rpcConn.logout()

def getNetwork(networks, name):
    """
    Get the network with a specific name. This method does not create a network 
    if no network exists with the given name.

    Arguments:
        networks -- Network objects for searching.
        name -- Name the network shall have.

    Returns:
        network object on success else None.
    """
    networks = [n for n in networks if n.getID() == name]
    if len(networks) == 0:
        return None
    else:
        return networks[0]

def getInterfaceRecord(networkRecords, mac):
    """
    Get the interface record of xen by it's mac.

    Arguments:
        interfaces -- Interfaces on xen server.
        mac -- Mac of the interface.

    Returns:
        network object on success else None.
    """
    interfaces = [rec for rec in networkRecords if networkRecords[rec]['MAC'] == mac]
    if len(interfaces) == 0:
        return None
    else:
        return interfaces[0]
