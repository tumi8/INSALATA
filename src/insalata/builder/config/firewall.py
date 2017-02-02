import os
import uuid
import json
import subprocess
from insalata.builder.decorator import builderFor
from insalata.helper.ansibleWrapper import addToKnownHosts

@builderFor(action="configureFirewall", template=["iptables"])
def configureIpTables(logger, host):
    """
    Set iptables firewall rules on this host.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: The target host that references firewall rules to set
    :type host: Host
    """
    target = host.getID() if host.getNameApplied() else host.getTemplate().getID()
    addToKnownHosts(target)

    #check if raw iptables are given with the hosts raw-attribute
    raw = host.getFirewallRaw()
    if raw and raw.getFirewall().lower() == "iptables":
        configureIpTablesRaw(logger, host.getID(), target, raw)
    else:
        configureIpTablesFromSimple(logger, host.getID(), target, host.getFirewallRules())

def configureIpTablesRaw(logger, hostId, target, raw):
    """
    Set iptables firewall rules from a raw dump.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param hostId: The identifier of the host that references firewall rules to set
    :type hostId: str

    :param target: The target name to use for the Ansible playbook.
    :type target: str

    :param raw: A raw firewall data dump to apply directly.
    :type raw: insalata.model.FirewallRule.FirewallRaw
    """

    #build json with the raw data
    data = {
        "target": target,
        "raw": raw.getData()
    }

    filename = str(uuid.uuid4()) + ".json"

    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{}] Configure firewall with raw data on machine named '{}'.".format(hostId, target))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/firewall/iptables_raw.yml --extra-vars "@' + filename + '"', shell=True)

    #remove json
    if os.path.exists(filename):
        os.remove(filename)

def configureIpTablesFromSimple(logger, hostId, target, simplerules):
    """
    Set iptables firewall rules from a list of simplified rules.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param hostId: The identifier of the host that references firewall rules to set
    :type hostId: str

    :param target: The target name to use for the Ansible playbook.
    :type target: str

    :param simplerules: A list of simplified rules to apply as iptable rules.
    :type simplerules: list(insalata.model.FirewallRule.FirewallRule)
    """

    #build json with all firewall rules
    data = {
        "target": target,
        "rules": [{
            "chain": r.getChain(),
            "action": r.getAction().upper(),
            "protocol": r.getProtocol(),
            "srcnet": r.getSrcNet(),
            "destnet": r.getDestNet(),
            "sports" : r.getSrcPorts(),
            "dports" : r.getDestPorts(),
            "in_interface": None if (not r.getInInterface()) else r.getInInterface().getID(),
            "out_interface": None if (not r.getOutInterface()) else r.getOutInterface().getID()
        } for r in simplerules]
    }

    filename = str(uuid.uuid4()) + ".json"

    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{0}] Configure firewall with simplified rules.".format(hostId))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/firewall/iptables_from_simple.yml --extra-vars "@' + filename + '" -v -c paramiko', shell=True)

    #remove json
    if os.path.exists(filename):
        os.remove(filename)