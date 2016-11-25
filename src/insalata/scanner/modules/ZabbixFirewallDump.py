from insalata.model.Host import Host
from insalata.model.Interface import Interface

import json, string, random, pyzabbix, urllib, urllib3, os, subprocess
import re

#Frage bzgl srcport
def scan(graph, connectionInfo, logger, thread):
    """
    Get all VMs that exist on a xen server.

    Necessary values:
        timeout
        name

        zabbixURL
        zabbixUser
        zabbixPassword
        firewallDumpValue (This value must return a firewall dump in the iptables-save syntax)
        (Optional) firewallTypeValue

    :param grpah: Data Interface object for this scanner
    :type graph: :class: `Graph`

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: seealso:: :class:`logging:Logger`

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """
    logger.info("Collecting firewall information using Zabbix Server")

    zabbixConnection = None
    timeout = int(connectionInfo['timeout'])
    name = connectionInfo['name']

    try:
        zabbixConnection = pyzabbix.ZabbixAPI(url=connectionInfo["zabbixURL"], user=connectionInfo["zabbixUser"], password=connectionInfo["zabbixPassword"])
    except urllib.error.URLError:
        logger.error("Can not connect to Zabbix Server {0}.".format(connectionInfo["zabbixURL"]))
        return
    except pyzabbix.api.ZabbixAPIException:
        logger.error("Username or password invalid for Zabbix Server {0}. User: {1}, Password: {2}.".format(connectionInfo["zabbixURL"], connectionInfo["zabbixUser"], connectionInfo["zabbixPassword"]))
        return


    for host in graph.getAllNeighbors(Host):
        try:
            param = {
                "filter" : {
                    "host" : host.getID()
                }
            }
            answer = zabbixConnection.do_request("host.get", param)
            if len(answer["result"]) == 0:
                continue

            logger.debug("Collecting firewall information using Zabbix for host {0}.".format(host.getID()))

            param = {
                "hostids" : answer["result"][0]["hostid"],
                "search" : {
                    "key_" : connectionInfo["firewallDumpValue"]
                }
            }
            answer = zabbixConnection.do_request("item.get", param)
            if len(answer["result"]) == 0:
                logger.error("Agent on host {0} does not support the key {1}. Zabbix Server: {2}".format(host.getID(), connectionInfo["firewallDumpValue"], connectionInfo["zabbixURL"]))
                continue

            firewallDump = answer["result"][0]["lastvalue"]

            #Test if firewall type is known
            if "firewallTypeValue" in connectionInfo:
                param = {
                    "hostids" : answer["result"][0]["hostid"],
                    "search" : {
                        "key_" : connectionInfo["firewallTypeValue"]
                    }
                }
                answer = zabbixConnection.do_request("item.get", param)
                if len(answer["result"]) == 0:
                    #Not supported
                    logger.debug("Key {0} not supported by agent of host {1}.".format(connectionInfo["firewallTypeValue"], host.getID()))
                    continue
                firewalType = answer["result"][0]["lastvalue"]

                raw = graph. getOrCreateFirewallRaw(name, timeout, host, firewalType, firewallDump)
                host.setFirewallRaw(raw)

            filename = ".firewallDump" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)) + ".tmp"
            with open(filename, 'r+') as dumpFile:
                dumpFile.write(firewallDump)

            for chain in getChains(firewallDump):
                p = subprocess.call(["/etc/insalata/template/fffuu/fffuu", ""], shell=True, stdout=subprocess.PIPE)
                out, _ = p.communicate()

                for rule in splitOutput(out):
                    inInterface = outInterface = None
                    if "inInterface" in rule:
                        interfaces = [i for i in host.getAllNeighbors(Interface) if i.getID() == rule["inInterface"]]
                        if len(interfaces) > 0:
                            inInterface = interfaces[0]
                        else:
                            logger.error("Could not find the correct inInterface({0}) for a firewall rule on host {1}.".format(rule["inInterface"], host.getID()))
                            continue

                    if "outInterface" in rule:
                        interfaces = [i for i in host.getAllNeighbors(Interface) if i.getID() == rule["outInterface"]]
                        if len(interfaces) > 0:
                            inInterface = interfaces[0]
                        else:
                            logger.error("Could not find the correct outInterface({0}) for a firewall rule on host {1}.".format(rule["outInterface"], host.getID()))
                            continue
                    rule = graph.getOrCreateFirewallRule(name, timeout, host, chain, rule["action"], rule["protocol"],  rule["source"],  rule["destination"], rule["srcports"], rule["destPorts"], inInterface, outInterface)
                    host.addFirewallRule(rule)
            os.remove(filename)
        except:
            logger.error("Error while gathering values from Zabbix Server {0}.".format(connectionInfo["zabbixURL"]))


def splitOutput(output):
    """
    Parse output of the fffuu haskel-tool.
    Keys in the list elements:
        - action
        - protocol
        - source
        - destination
        - source
        - inInterface (Optional)
        - outInterface (Optional)
        - destPorts (Optional)
        - srcPorts (Optional)

    :param output: Output of fffuu
    :type output: str

    :returns: List of dictionaries with the content of each firewall rule
    :rtype: list<dict>
    """
    output = re.split("== to simple firewall ==", output)[1]
    output = re.split("== to even-simpler firewall ==", output)[0]

    result = list()
    for line in re.split("\n", output):
        splitted = [match.group(0) for match in re.finditer(r"([A-Z]+)|([a-zA-Z]+\s)|(\d+\.\d+\.\d+\.\d+/\d+)|(((dports:)|(sports:)) \d+(:\d+)?)|(((out:)|(in:)) [\.a-zA-Z0-9]+)", line)]
        if len(splitted) > 0:
            part = {
                "action" : splitted[0],
                "protocol" : splitted[1].replace(" ", ""),
                "source" : splitted[2],
                "destination" : splitted[3],
                "inInterface" : None,
                "outInterface" : None,
                "destPorts" : None,
                "srcPorts" : None
            }
            if len(splitted) > 4:
                for match in splitted[4:]:
                    if "in:" in match:
                        part["inInterface"] = match[4:]
                    if "out:" in match:
                        part["outInterface"] = match[5:]
                    if "dports:" in match:
                        match = match[8:]
                        if ":" in match:
                            r = re.split(":", match)
                            part["destPorts"] = list(range(int(r[0]), int(r[1]) + 1))
                        else:
                            part["destPorts"] = [int(match)]
                    if "srcports:" in match:
                        match = match[8:]
                        if ":" in match:
                            r = re.split(":", match)
                            part["srcports"] = list(range(int(r[0]), int(r[1]) + 1))
                        else:
                            part["srcports"] = [int(match)]
            result.append(part)
    return result

def getChains(dump):
    """
    Get all chains used in the firewall.

    :param dump: iptables-save dump
    :type dump: str

    :returns: Set of all chains used in the dump
    :rtype: set
    """
    return set(re.findall(r":[A-Z]+", dump))

