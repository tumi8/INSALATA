from configobj import ConfigObj
import xmlrpc.client
import os
from insalata.model.Location import LOCATIONS_CONF

def getXenConnection(server, logger):
    """
    Establish a connection with the given XenServer using XML-RPC

    :param server: The name of the server as specified in the global config file. 
    :type server: str

    :param logger: The logger for logging possible error messages during the connection buildup
    :type logger: seealso:: :class:`logging:Logger`

    :returns: A tuple with xen-object, session-instance and a storage reference
    :rtype: (ServerProxy, str, str)
    """
    
    server = server.lower()

    #read the global 'locations' file with all information
    if os.path.isfile(LOCATIONS_CONF):

        try:
            locationConf = ConfigObj(LOCATIONS_CONF)
            
            #check if the server is specified
            if server in locationConf:
                serverConf = locationConf[server]

                #check if all necessary information for this server is given
                if not "uri" in serverConf:
                    logger.error("No URI for Xen Server named '{0}' found in '{1}'".format(server, LOCATIONS_CONF))
                    return None
                if not "login_id" in serverConf:
                    logger.error("No login_id for Xen Server named '{0}' found in '{1}'".format(server, LOCATIONS_CONF))
                    return None
                if not "login_pass" in serverConf:
                    logger.error("No login_pass for Xen Server named '{0}' found in '{1}'".format(server, LOCATIONS_CONF))
                    return None
                if not "xen_storage" in serverConf:
                    logger.error("No xen_storage for Xen Server named '{0}' found in '{1}'".format(server, LOCATIONS_CONF))
                    return None

                uri = serverConf["uri"]
                user = serverConf["login_id"]
                password = serverConf["login_pass"]
                storage = serverConf["xen_storage"]

                #establish an XMLRPC connection using the login information
                xen = xmlrpc.client.Server(uri)
                session = xen.session.login_with_password(user, password)
                if session['Status'] == 'Failure':
                    logger.error("Error while establishing an RPC connection with '{0}'. Error: {1}.".format(uri, str(session['ErrorDescription'])))
                    return None

                session = session['Value']

                #get the storage
                result = xen.SR.get_by_name_label(session, storage)
                if result['Status'] == 'Failure':
                    logger.error("Error while retrieving the storage named '{0}'. Error: {1}.".format(storage, str(result['ErrorDescription'])))
                    return None

                if len(result['Value']) == 0:
                    logger.error("The storage named '{0}' was not found.".format(storage))
                    return None
                sr = result['Value'][0]

                return (xen, session, sr)
        except Exception as ex:
            logger.critical("Error reading locations.conf: {0}".format(str(ex)))
            raise ex

        err = "No connection information for Xen Server named '{0}' found in '{1}'".format(server, LOCATIONS_CONF)
        logger.critical(err)
        raise Exception(err)
    else:
        err = "No locations.conf found in '{0}'".format(LOCATIONS_CONF)
        logger.critical(err)
        raise Exception(err)
