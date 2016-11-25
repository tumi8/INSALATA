
from insalata import RpcConnection
from insalata.model.Layer2Network import Layer2Network
import json

def scan(graph, connectionInfo, logger, thread):
    """
    Get networks on XenServer. Updates the networks list in data.

    :param grpah: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """

    logger.info("Reading networks on server:{0}".format(connectionInfo['xenuri']))

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
    answer = xen.network.get_all_records(session)
    if answer['Status'] == 'Failure':
        logger.error("Network scan on Xen server {0} failed. Server sent failure while reading all networks.".format(connectionInfo['xenuri']))
        return
    networkRecords = answer['Value']


    networksOnServer = set([networkRecords[record]['name_label'] for record in networkRecords if not networkRecords[record]['name_label'].startswith("Pool")])
    stillExistingNetworks = set()
    deletedNetworks = set()
    currentNetworks = graph.getAllNeighbors(Layer2Network)
    for network in currentNetworks:
        if network.getGlobalID() in networksOnServer:
            stillExistingNetworks.add(network)
        else:
            deletedNetworks.add(network)
        networksOnServer.remove(network.getGlobalID())

    for network in deletedNetworks:
        network.removeVerification(name)

    for network in networksOnServer:
        if network != "controll-network":
            stillExistingNetworks.add(graph.getOrCreateLayer2Network(network, name, timeout))

    for network in stillExistingNetworks:
        logger.debug("Scanning network {0}".format(network.getID()))
        network.verify(name, timeout)

        answer = xen.network.get_by_name_label(session, network.getGlobalID())
        if answer['Status'] == 'Failure':
            logger.error("Host scan on Xen server {0} failed. Server sent failure while getting record for: {1}.".format(connectionInfo['xenuri'], network.getGlobalID()))
            continue
        if len(answer['Value']) == 0:
            logger.error("Host scan on Xen server {0} failed. Server has no record for: {1}.".format(connectionInfo['xenuri'], network.getGlobalID()))
            continue
        record = answer['Value'][0]


        answer = xen.network.get_other_config(session, record)
        if answer['Status'] == 'Failure':
            logger.error("Host scan on Xen server {0} failed. Server sent failure while getting other config from: {1}.".format(connectionInfo['xenuri'], network.getGlobalID()))
            continue
        otherConfig = answer['Value']

        if "configs" in list(otherConfig.keys()):
            network.setConfigNames(list(json.loads(otherConfig["configs"])))
    rpcConn.logout()