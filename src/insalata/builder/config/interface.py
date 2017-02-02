import os
import uuid
import json
import subprocess
from insalata.builder.decorator import builderFor
from insalata.helper.ansibleWrapper import addToKnownHosts

@builderFor(action="configureInterface", template=["ubuntu"])
def configureInterfaceAnsibleDebian(logger, interface):
    """
    Configure a single interface on the host

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`
    
    :param interface: The interface to configure
    :type interface: Interface
    """
    host = interface.getHost()
    target = host.getID() if host.getNameApplied() else host.getTemplate().getID()
    addToKnownHosts(target)

    #build json with host.template, host.id and host.interfaces
    data = {
        "target": target,
        "interfaces": [{
            "iface": interface.getID(),
            "type": "interface",
            "inet": "dhcp" if interface.isDhcp() else "static",
            "gateway": None if interface.isDhcp() else list(interface.getAddresses())[0].getGateway(),
            "addresses": None if interface.isDhcp() else list(interface.getAddresses())[0].getID() + "/" + str(list(interface.getAddresses())[0].getPrefix())
        }]
    }

    filename = str(uuid.uuid4()) + ".json"
    
    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{0}] Configure interface {1} on machine named '{2}'.".format(host.getID(), interface.getID(), target))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/interfaces/debian_interfaces.yml --extra-vars "@' + filename + '" -v -c paramiko', shell=True)

    #remove json
    if os.path.exists(filename):
        os.remove(filename)

@builderFor(action="unconfigureInterface", template=["ubuntu"])
def unconfigureInterfaceAnsibleDebian(logger, interface):
    """
    Remove/unconfigure a single interface on the host

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`
    
    :param interface: The interface to unconfigure
    :type interface: Interface
    """
    host = interface.getHost()
    target = host.getID() if host.getNameApplied() else host.getTemplate().getID()
    addToKnownHosts(target)

    #build json with host.template, host.id and host.interfaces
    data = {
        "target": target,
        "interfaces": [{
            "iface": interface.getID(),
            "type": "interface",
            "inet": "dhcp" if interface.isDhcp() else "static",
            "delete": True
        }]
    }

    filename = str(uuid.uuid4()) + ".json"
    
    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{0}] Unconfigure interface {1} on machine named '{2}'.".format(host.getID(), interface.getID(), target))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/interfaces/debian_interfaces.yml --extra-vars "@' + filename + '"', shell=True)

    #remove json
    if os.path.exists(filename):
        os.remove(filename)
