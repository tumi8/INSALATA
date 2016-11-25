import os
import uuid
import json
import subprocess
from insalata.builder.decorator import builderFor
from insalata.helper.ansibleWrapper import addToKnownHosts

#Configure Hostname and Interfaces on a machine
@builderFor(action="name")
def configureHostname(logger, host):
    """
    Configure the hostname of a host

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`
    
    :param host: Host to set the hostname of
    :type host: Host
    """
    target = host.getID() if host.getNameApplied() else host.getTemplate().getID()
    addToKnownHosts(target)

    #build json with parameters
    data = {
        "target": target,
        "name": host.getID()
    }
        
    filename = str(uuid.uuid4()) + ".json"
    
    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{0}] Set hostname to '{1}'".format(host.getID(), host.getID()))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/hostname/hostname.yml --extra-vars "@' + filename + '"', shell=True)

    #remove json
    if os.path.exists(filename):
        os.remove(filename)