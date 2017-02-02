import os
import uuid
import json
import subprocess
import itertools
from insalata.builder.decorator import builderFor
from insalata.helper.ansibleWrapper import addToKnownHosts
from insalata.model.DhcpService import DhcpService
from insalata.model.DnsService import DnsService

@builderFor(action="configureDhcp", template=["dnsmasq"], service="dhcp")
def configureDnsmasqDhcp(logger, service, config):
    configureDnsmasq(logger, service, config)

@builderFor(action="unconfigureDhcp", template=["dnsmasq"], service="dhcp")
def unconfigureDnsmasqDhcp(logger, service, config):
    configureDnsmasq(logger, service, config)  #just reapply the configuration, now with missing DHCP interface

@builderFor(action="configureDns", template=["dnsmasq"], service="dns")
def configureDnsmasqDns(logger, service, config):
    configureDnsmasq(logger, service, config)

@builderFor(action="unconfigureDns", template=["dnsmasq"], service="dns")
def unconfigureDnsmasqDns(logger, service, config):
    #stop dnsmasq
    stopServiceAnsible(logger, service.getHost().getGlobalID(), "dnsmasq")

def configureDnsmasq(logger, service, config):
    """
    Configure DNS and DHCP using dnsmasq on a Debian-based machine.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`
    
    :param service: A reference to the service (the complete host will be used)
    :type service: Service

    :param config: The configuration holding all other elements
    :type config: Graph
    """
    
    host = service.getHost()
    target = host.getID() if host.getNameApplied() else host.getTemplate().getID()
    addToKnownHosts(target)

    #find all definitions of this host as DNS server (all DnsServices on all IPs of all interfaces)
    ips = list(itertools.chain(*[i.getAddresses() for i in host.getInterfaces()]))
    dnss = list(itertools.chain(*[ip.getAllNeighbors(type=DnsService) for ip in ips]))
    #find all definitions of this host as DHCP server
    dhcps = list(itertools.chain(*[ip.getAllNeighbors(type=DhcpService) for ip in ips]))

    #Only one DNS allowed, as dnsmasq can't handle multiple domains
    if (len(dnss) > 0) and (not (all(x.getDomain() == dnss[0].getDomain() for x in dnss))):
        logger.error("[{0}] DNS Server found in multiple networks/domains. Only one allowed due to the limitations of dnsmasq.".format(host.getID()))
        return

    #DHCP without DNS on an interface is not possible with dnsmasq
    if any(x.getInterface().getID() not in [d.getInterface().getID() for d in dnss] for x in dhcps):
        logger.error("[{0}] DHCP without DNS on an interface is not possible with dnsmasq.".format(host.getID()))
        return
    
    #get associated host interface
    dhcpInterfaces = [(d.getInterface(), d) for d in dhcps]
    dnsInterfaces = [(d.getInterface(), d) for d in dnss]

    #find interfaces without dhcp
    #dns_only = filter(lambda x: x[1].getInterface().getID() not in [d.getInterface().getID() for d in dhcps], dnsInterfaces)
    dns_only = [x for x in dnsInterfaces if x[1].getInterface().getID() not in [d.getInterface().getID() for d in dhcps]]
    #dns_only = map(lambda x: x[0].getID(), dns_only)
    dns_only = [x[0].getID() for x in dns_only]

    #find all other DNS servers and connect them as string for dnsmasq
    otherDnsServer = ""
    #for every DNS server, get its domain and ip 
    for h in config.getHosts():
        for i in h.getInterfaces():
            for ip in i.getAddresses():
                for d in ip.getAllNeighbors(type=DnsService):
                    serverString = "server=/" + d.getDomain() + "/" + ip.getID() + "\n"
                    if not serverString in otherDnsServer:
                        otherDnsServer += serverString
                        #todo: now the configured dns appear in their own files, if issues occur -> change

    #build json with hostname, domain, dhcp interface, dhcp range, dhcp lease and the gateway's ip
    data = {
        "domain": dnsInterfaces[0][1].getDomain(),  #domain identical on all interfaces
        "target": target,
        "dns_only": dns_only,
        "interfaces": [{
            "interface": i[0].getID(),
            "name": host.getID(),   #used for interface-name option, therefore the host name is necessary
            "dhcp_range_start": i[1].getDhcpRangeStart(),
            "dhcp_range_end": i[1].getDhcpRangeEnd(),
            "dhcp_lease": i[1].getLease(),
            "gateway": i[1].getAnnouncedGateway() if i[1].getAnnouncedGateway() else "{{ ansible_" + i[0].getID() + ".ipv4.address }}"
        } for i in dhcpInterfaces],
        "other": otherDnsServer
    }
    
    filename = str(uuid.uuid4()) + ".json"

    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{}] Configure dnsmasq on machine named '{}'.".format(host.getID(), target))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/dnsdhcp/dnsmasq.yml --extra-vars "@' + filename + '" -v -c paramiko', shell=True)
    
    #remove json
    if os.path.exists(filename):
        os.remove(filename)

def stopServiceAnsible(logger, hostName, serviceName):
    """
    Stop a service with the given name

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`
    
    :param hostName: The name of the host to stop the service on.
    :type hostName: str

    :param serviceName: The name of the service to stop.
    :type serviceName: str
    """

    #build json with parameters
    data = {
        "target": hostName,
        "service": serviceName
    }
        
    filename = str(uuid.uuid4()) + ".json"
    
    with open(filename, 'w') as outfile:
        json.dump(data, outfile)

    #run with json
    logger.info("[{0}] Stop dnsmasq".format(hostName))
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/services/stop_service.yml --extra-vars "@' + filename + '"', shell=True)

    #remove json
    if os.path.exists(filename):
        os.remove(filename)
