from insalata.model.Host import Host
from insalata.helper import SnmpWrapper
from ipaddress import IPv4Address
from insalata.model.Interface import Interface

def scan(graph, connectionInfo, logger, thread):
    """
    Collect routing information using SNMP.
    
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
    logger.info("Collecting routing information using SNMP")

    user = connectionInfo["user"]
    authPass = connectionInfo["passwordMD5"]
    encPass = connectionInfo["passwordDES"]
    port = int(connectionInfo["port"]) if "port" in connectionInfo.keys() else 161
    name = connectionInfo["name"]
    timeout = int(connectionInfo["timeout"])

    for host in graph.getAllNeighbors(Host):
        if not ((host.getPowerState() is None) or (host.getPowerState() == 'Running')):
            continue
        logger.debug("Collecting routing information from host: {0}".format(host.getID()))

        request = SnmpWrapper.SnmpWrapper(host.getID(), user, authPass, encPass, port)

        answer = SnmpWrapper.checkReturnSnmp(request.getValue(SnmpWrapper.Values["hostForwarding"]), host, name, user, logger)
        if answer:
            if(answer[1] == 0):
                logger.debug("Host '{0}' does not forward IP packets.".format(host.getID()))
                continue
            answer = SnmpWrapper.checkReturnSnmp(request.walkOid(SnmpWrapper.Values["destRoute"]), host, name, user, logger)
            if not answer:
                logger.error("No destination address available for host: {0}.".format(host.gedID()))
                continue
            for oid, destAddress in answer:
                identifier = SnmpWrapper.OidToRouteIdentifier(oid)
                mac = netmask = interface = hop = None

                answer = SnmpWrapper.checkReturnSnmp(request.getValue(SnmpWrapper.Values["interfaceIndex"], identifier), host, name, user, logger)
                if not answer:
                    logger.error("No interface is specified for route on host {0}; OID: {1}; Collector: {2}.".format(host.getID(), oid, name))
                    continue
                interfaceIndex = answer[1]

                answer = SnmpWrapper.checkReturnSnmp(request.getValue(SnmpWrapper.Values["mac"], interfaceIndex), host, name, user, logger)
                if not answer:
                    logger.error("No mac available for interface index {0} on host {1}; Collector: {2}.".format(interfaceIndex, host.getID(), name))
                    continue
                mac = answer[1]._value
                mac = ":".join([format(c, "x").zfill(2) for c in mac])
                interfaces = [i for i in graph.getAllNeighbors(Interface) if i.getMAC() == mac]
                if len(interfaces) == 0:
                    logger.error("No suitable interface found for mac '{0}' on host {1}; Collector: {2}.".format(mac, host.getID(), name))
                    interface = None
                else:
                    interface = interfaces[0]

                answer = SnmpWrapper.checkReturnSnmp(request.getValue(SnmpWrapper.Values["netmask"], identifier), host, name, user, logger)
                if not answer:
                    logger.error("No netmask specified on route with oid '{0}'' on host{1}; Collector: {2}".format(oid, host.getID(), logger))
                    continue
                netmask = answer[1]

                answer = SnmpWrapper.checkReturnSnmp(request.getValue(SnmpWrapper.Values["nextHop"], identifier), host, name, user, logger)
                if not answer:
                    logger.error("No hop specified on route with oid '{0}' on host{1}; Collector: {2}".format(oid, host.getID(), logger))
                    continue
                hop = answer[1]

                if hop == "0.0.0.0":
                    continue
                    

                route = graph.getOrCreateRoute(name, timeout, host, destAddress, netmask, hop, interface)
                route.verify(name, timeout)

                host.addRoute(route)
                logger.debug("Added new/verified route to/of host {0}.".format(host.getID()))
