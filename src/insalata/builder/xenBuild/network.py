import json
import time
from insalata.builder.xenBuild.xenHelper import getXenConnection
from insalata.builder.decorator import builderFor

def findNetwork(network, logger, xen, session):
    """
    Find this networks's reference in Xen (based on its ID). 

    :param network: Network-instance to find a Xen reference for.
    :type network: Network

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param xen: A xmlrpc reference to xen 
    :type xen: ServerProxy

    :param session: A session for the xen XML-RPC reference. 
    :type session: str

    :returns: A reference to the network in Xen if it exists, otherwise None
    :rtype: str
    """
    request = xen.network.get_by_name_label(session, network.getID())
    if "Value" in request and len(request['Value']) == 1:
        return request['Value'][0]
    else:
        logger.debug("Network named '{0}' not found.".format(network.getID()))
        return None

#create the network
@builderFor(action="createNetwork", hypervisor="xen")
def create(logger, network):
    """
    Create the given network in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param network: Network-instance to create.
    :type network: Network
    """
    con = getXenConnection(network.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    ref = findNetwork(network, logger, xen, session)
    if ref:
        logger.warning("The network named '{0}' exists already!".format(network.getID()))
    else:
        #build a record object contarootining all information about the network
        net_record = {
            'name_label': network.getID(),
            'name_description': 'Network created by auto-config : ' + time.strftime("%c"),
            'mTU': 1500,    #note: mTU instead of MTU, seems to be a bug in XE...
            'other_config': {},
            'tags': []
        }

        logger.info("Create network '{0}'...".format(network.getID()))
        result = xen.network.create(session, net_record)
        if result['Status'] == 'Failure':
            logger.error("[{0}] Network not created. Error: {1}".format(network.getID(), str(result['ErrorDescription'])))

#Add a new config to the list of configs this network is a member of
@builderFor(action="addConfigNameNetwork", hypervisor="xen")
def insertConfigName(logger, network, configId):
    """
    Add the given config identifier to the network's tags in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param network: Network-instance to modify.
    :type network: Network

    :param configId: An identifier for the configuration this network is now part of.
    :type configId: str
    """
    con = getXenConnection(network.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    ref = findNetwork(network, logger, xen, session)
    if ref:
        result = xen.network.get_other_config(session, ref)
        if result['Status'] == "Failure":
            logger.warning("Error while getting other config of network '{0}'. Error: {1}.".format(network.getID(), str(result['ErrorDescription'])))
            return
        otherConfig = result['Value']

        #get the current configs in the networks's 'other_config'
        configsArray = []
        if "configs" in otherConfig:
            configsArray = json.loads(otherConfig['configs'])
        #add the name of the config to the networks's list
        if not configId in configsArray:
            configsArray.append(configId)
        xen.network.remove_from_other_config(session, ref, "configs")
        xen.network.add_to_other_config(session, ref, "configs", json.dumps(configsArray))
    else:
        logger.warning("The network named '{0}' not found!".format(network.getID()))

#Remove a config from the list of configs in which this network is a part of
@builderFor(action="removeConfigNameNetwork", hypervisor="xen") 
def removeConfigName(logger, network, configId):
    """
    Remove the given config identifier from the network's tags in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param network: Network-instance to modify.
    :type network: Network

    :param configId: An identifier for the configuration this network is removed from.
    :type configId: str
    """
    con = getXenConnection(network.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    ref = findNetwork(network, logger, xen, session)
    if ref:
        result = xen.network.get_other_config(session, ref)
        if result['Status'] == "Failure":
            logger.warning("Error while getting other config of network '{0}'. Error: {1}.".format(network.getID(), str(result['ErrorDescription'])))
            return
        otherConfig = result['Value']

        if "configs" in otherConfig:
            configsArray = json.loads(otherConfig['configs'])
            if configId in configsArray:
                configsArray.remove(configId)
        xen.network.remove_from_other_config(session, ref, "configs")
        xen.network.add_to_other_config(session, ref, "configs", json.dumps(configsArray))
        return configsArray
    else:
        logger.warning("The network named '{0}' not found!".format(network.getID()))
        return []

#Remove a network from the xen server
@builderFor(action="removeNetwork", hypervisor="xen")
def destroy(logger, network):
    """
    Destroy the given network in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param network: Network-instance to remove.
    :type network: Network
    """
    con = getXenConnection(network.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con
    
    ref = findNetwork(network, logger, xen, session)
    if ref:
        #destroy the network
        destroyRequest = xen.network.destroy(session, ref)
        if destroyRequest['Status'] == 'Failure':
            logger.error("Error while deleting network " + network.getID() + ". Error: " + str(destroyRequest['ErrorDescription']))
