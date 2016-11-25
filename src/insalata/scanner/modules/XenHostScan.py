import json
from insalata import RpcConnection
from insalata.model.Location import Location
from insalata.model.Host import Host
from insalata.model.Template import Template

def scan(graph, connectionInfo, logger, thread):
    """
    Get all VMs that exist on a xen server.

    :param grpah: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """
    DEFAULT_TEMPLATE = "host-base"
    logger.info("Reading hosts on xen server: {0}".format(connectionInfo['xenuri']))

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

    answer = xen.VM.get_all_records(session) #Get all VMs on the server
    if answer['Status'] == 'Failure':
        logger.error("Host scan on Xen server {0} failed. Server sent failure while reading all vms.".format(connectionInfo['xenuri']))
        return
    hostRecords = answer['Value']

    location = graph.getOrCreateLocation(connectionInfo['xenname'], name, timeout)
    location.verify(name, timeout)

    hostsOnServer = set()
    #Get a list of all hosts on this server
    for record in hostRecords:
        if not (hostRecords[record]['is_a_template'] or hostRecords[record]['is_a_snapshot'] or hostRecords[record]['is_control_domain']):
            hostsOnServer.add(hostRecords[record]['name_label'])

    currentHosts = graph.getAllNeighbors(Host)
    deletedHosts = set()
    stillExistingHosts = set()
    for host in currentHosts:
        if host.getGlobalID() in hostsOnServer:
            stillExistingHosts.add(host)
        else:
            deletedHosts.add(host)
        hostsOnServer.remove(host.getGlobalID()) #Determine which hosts are new

    for host in deletedHosts:
        host.removeVerification(name)

    #Create the new hosts in the internal data structure
    #Other parameters will be set later -> Add them to still existing ones
    for hostname in hostsOnServer:
        stillExistingHosts.add(graph.getOrCreateHost(hostname, name, timeout, location=location))

    for host in stillExistingHosts:
        logger.debug("Starting host scan: {0}".format(host.getID()))
        host.verify(name, timeout)
        host.setLocation(location)

        answer = xen.VM.get_by_name_label(session, host.getGlobalID())
        if answer['Status'] == 'Failure':
            logger.error("Host scan on Xen server {0} failed. Server sent failure while getting record for: {1}.".format(connectionInfo['xenuri'], host.getGlobalID()))
            continue
        if len(answer['Value']) == 0:
            logger.error("Host scan on Xen server {0} failed. Server has no record for: {1}.".format(connectionInfo['xenuri'], host.getGlobalID()))
            continue
        record = answer['Value'][0]


        answer = xen.VM.get_other_config(session, record)
        if answer['Status'] == 'Failure':
            logger.error("Host scan on Xen server {0} failed. Server sent failure while getting other config from: {1}.".format(connectionInfo['xenuri'], host.getGlobalID()))
            continue
        otherConfig = answer['Value']


        if "template" in list(otherConfig.keys()):
            templateStr = otherConfig['template']
        else:
            templateStr = DEFAULT_TEMPLATE

        template = [t for t in location.getTemplates() if t.getID() == templateStr]
        if len(template) > 0:
            host.setTemplate(template[0])
        else:
            logger.error("Unknown template '{0}' for location {1}. Please check /etc/insalata/locations.conf.".format(templateStr, location.getID()))

        host.setPowerState(hostRecords[record]['power_state'])

        if "configs" in otherConfig:
            host.setConfigNames(list(json.loads(otherConfig["configs"])))

    rpcConn.logout()