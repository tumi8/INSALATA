import os
import uuid
import json
import subprocess
from insalata.builder.decorator import builderFor
from insalata.helper.ansibleWrapper import addToKnownHosts

@builderFor(action="configureRouting", template=["ubuntu", "router"])
def configureRouting(logger, host):
    """
    Set routing table on this host.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: The target host that references routing table entries
    :type host: Host
    """
    target = host.getID() if host.getNameApplied() else host.getTemplate().getID()
    addToKnownHosts(target)

    #build json with all routes
    data = {
        "target": target,
        "routes": [{
            "network": r.getDestination(),
            "mask": r.getPrefix(),
            "next": r.getGateway()
        } for r in host.getRoutes()]
    }

    filename = str(uuid.uuid4()) + ".json"

    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{}] Configure routing on machine named '{}'.".format(host.getID(), target))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/routing/debian_routing.yml --extra-vars "@' + filename + '" -v -c paramiko', shell=True)

    #remove json
    if os.path.exists(filename):
        os.remove(filename)