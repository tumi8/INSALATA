from insalata.model.Host import Host
from insalata.helper import SnmpWrapper
from insalata.model.Interface import Interface

def scan(graph, connectionInfo, logger, thread):
    """
    Collect interface information using SNMP.
    
    Necessary values in the configuration file of this collector module:
        - timeout       Timeout this collector module shall use (Integer)
        - user          Username used for the SNMP login on the remote devices
        - passwordMD5   MD5 SNMP authentication password
        - passwordDES   DES SNMP encryption password
        - port          (Optional) Port the module shall use for the SNMP connection. Default is 161
    
    :param graph: Data interface object for this collector module
    :type graph: insalata.model.Graph.Graph

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: logging:Logger

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """
    logger.info("Collecting interface information using SNMP")

    user = connectionInfo["user"]
    authPass = connectionInfo["passwordMD5"]
    encPass = connectionInfo["passwordDES"]
    port = int(connectionInfo["port"]) if "port" in connectionInfo.keys() else 161
    name = connectionInfo["name"]
    timeout = int(connectionInfo["timeout"])

    for host in graph.getAllNeighbors(Host):
        if not ((host.getPowerState() is None) or (host.getPowerState() == 'Running')):
            continue
        logger.debug("Collecting interface information from host: {0}".format(host.getID()))

        request = SnmpWrapper.SnmpWrapper(host.getID(), user, authPass, encPass, port)

        answer = SnmpWrapper.checkReturnSnmp(request.walkOid(SnmpWrapper.Values["mac"]), host, name, user, logger)
        if not answer:
            logger.error("No Interfaces available for host: {0}.".format(host.getID()))
            continue

        existingInterfaces = set()
        for _, mac in answer:
            logger.debug("Got SNMP reply: {}".format(str(answer)))
            mac = ":".join([format(ord(c), "x").zfill(2) for c in str(mac)])
            if mac != "":
                interface = graph.getOrCreateInterface(mac, name, timeout)
                host.addInterface(interface)
                existingInterfaces.add(interface)

        # Remove all interfaces that exist in the graph but not on the host
        for interface in host.getAllNeighbors(Interface):
            if interface not in existingInterfaces:
                interface.removeVerification(name)
