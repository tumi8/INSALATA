import itertools
import subprocess
import uuid
import insalata.builder.Builder
import os, sys
from insalata.Insalata import CONF_FILE
from insalata.model.DhcpService import DhcpService
from insalata.model.DnsService import DnsService
from insalata.model.Disk import Disk
from insalata.planning.FastDownwardParser import FastDownwardParser 
from configobj import ConfigObj

PLANNING_BASE = "/etc/insalata/template/planning"
PLANNING_TMP = "/etc/insalata/tmp"
DOMAIN_PATH = os.path.join(PLANNING_BASE, "testbed_domain.pddl")

def getPlan(logger, oldConfig, newConfig, diff):
    """
    Get an ordered execution plan of functions based on the newConfig and the diff-dictionary given.

    Keyword arguments:
        oldConfig -- Configuration representing current (or 'old') testbed state
        newConfig -- Configuration representing new testbed state
        diff -- dictionary listing all properties that changed between the old and the new configuration for each object
    """

    uid = uuid.uuid4()

    #first, get a dict with all objects (hosts, networks, interfaces) by their name
    objects = getObjectDict(oldConfig, newConfig)

    #create a pddl problem file
    problemFile = toPddlProblem(diff, objects, uid)
    #run solver with output file
    planFile = os.path.join(PLANNING_TMP, "plan_" + str(uid))

    logger.info("Run planner with problem file '{0}'".format(problemFile))

    # ---------------- PLANNER DEPENDENT SECTION ----------------
    #get the path to the planner (fast-downward) from the insalata.conf
    mainConf = ConfigObj(CONF_FILE)
    if "plannerPath" in mainConf:
        plannerPath = mainConf["plannerPath"]
    else:
        logger.critical("No plannerPath found in main config '{0}'".format(insalata.Insalata.CONF_FILE))
        return []

    #get the correct parser
    planParser = FastDownwardParser() 

    subprocess.call("{0} --plan-file {1} {2} {3} --search \"eager_greedy(ff(), preferred=ff())\"".format(plannerPath, planFile, DOMAIN_PATH, problemFile), shell=True)

    logger.info("CALLING: {0} --plan-file {1} {2} {3} --search \"eager_greedy(ff(), preferred=ff())\"".format(plannerPath, planFile, DOMAIN_PATH, problemFile))
    # ------------------------------------------------------------

    #process the plan-file by mapping the planner output to method calls
    
    #if there was a solution, there is a planFile
    if os.path.exists(planFile):
        logger.info("Plan found!")

        #remove problemFile
        if os.path.exists(problemFile):
            os.remove(problemFile)

        #get a matching function pointer to all lines
        #list all function names
        functionNames = [f for f in dir(insalata.builder.Builder.Builder) if not f.startswith('_')]
        #create tuples with name and pointer
        functions = [(f, getattr(insalata.builder.Builder.Builder, f)) for f in functionNames]
        #create dictionary with lowercase name
        functionDict = {key.lower(): value for (key, value) in functions}

        plan = planParser.parsePlan(objects, functionDict, planFile)

        #remove planFile
        if os.path.exists(planFile):
            os.remove(planFile)

        return plan
    else:
        logger.info("No plan found!")

    return []


def toPddlProblem(diff, state, uid):
    """
    Translate the differences between two configuration files into a PDDL problem file.
    This will return the filename of the new created PDDL problem.

    Keyword arguments:
        diff -- dictionary listing all elements and how they changed between 
                the old and the new configuration
        state -- All objects associated with their name
        uid -- unique identifier used in file name (to be concise with the resulting plan)
    """

    filename = os.path.join(PLANNING_TMP, "problem_" + str(uid))
    with open(filename, 'w') as outfile:
        #write fixed header
        outfile.write('(define (problem ' + filename + ')\n')
        outfile.write('\t(:domain testbed)\n')

        writeObjects(outfile, diff, state)
        writeInit(outfile, diff, state)
        writeGoal(outfile)

        outfile.write(')\n') #closing brace for (define) (problem ...)
        
    return filename


def writeObjects(outfile, diff, objects):
    """
    Write all objects (networks, hosts, server, router) existing in the new 
    configuration as objects existing in the PDDL problem.

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        diff -- dictionary listing all properties that changed between the old and the new configuration for each object
        state -- All objects associated with their name
    """

    #list all objects for the problem file including their type
    outfile.write('\t(:objects\n')
    #write networks
    for n in diff['l2networks']:
        outfile.write('\t\t' + n[0] + ' - network\n')

    #write hosts
    for h in diff['hosts']:
        host = objects[h[0]]    #todo: to lower is consequently necessary to compare with objects!!!!
        #write the correct pddl type based on the template
        outfile.write('\t\t' + h[0] + ' - ' + getPddlType(host.getTemplate()) + '\n')

        #write interfaces
        if "interfaces" in h[1]: 
            for i in h[1]['interfaces']['elements']:
                outfile.write('\t\t' + i[0] + ' - interface\n')

        #write dns/dhcp if there is any interface on this host, that this host acts as DNS/DHCP server on
        #get all ips of this host
        ips = list(itertools.chain(*[i.getAddresses() for i in host.getInterfaces()]))
        #get all services
        services = list(itertools.chain(*[ip.getServices() for ip in ips]))
        for s in services:
            if isinstance(s, DhcpService):
                outfile.write('\t\t' + s.getGlobalID() + ' - dhcp\n')
            elif isinstance(s, DnsService):
                outfile.write('\t\t' + s.getGlobalID() + ' - dns\n')
            else:
                outfile.write('\t\t' + s.getGlobalID() + ' - service\n')

    #write disks by using the objects dictionary in order to avoid duplicates (type is easy)
    for k, v in list(objects.items()):
        if isinstance(v, Disk):
            outfile.write('\t\t' + k + ' - disk\n')

    outfile.write('\t)\n') #closing brace for (:objects)


def writeInit(outfile, diff, state):
    """
    Specify the initial state of all objects in the new configuration file, 
    depending on how they have changed compared to the old config (diff)

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        diff -- dictionary listing all properties that changed between
                the old and the new configuration for each object
        state -- All objects associated with their name
    """

    outfile.write('\t(:init')

    #optional for metric
    outfile.write('\n\t(= (total-cost) 0)')

    writeInitHosts(outfile, diff, state)
    writeInitNetworks(outfile, diff, state)

    outfile.write('\n\t)\n') #closing brace for (:init)


def writeInitHosts(outfile, diff, state):
    """
    Specify the initial state of all hosts and interfaces in the new configuration file, 
    depending on how they have changed compared to the old config (diff)

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        diff -- dictionary listing all properties that changed between 
                the old and the new configuration for each object
        state -- All objects associated with their name
    """

    #inclues new, removed and existing hosts
    for h in diff['hosts']:
        hostname = h[0]
        hostObject = state[hostname] #state

        #set initial power state
        if not h[1]['powerState']['diff'] == "new" and hostObject.getPowerState().lower() == "running":
            outfile.write(' (running {0})'.format(hostname)) 
        elif not h[1]['powerState']['diff'] == "new" and hostObject.getPowerState().lower() == "halted":
            outfile.write(' (running {0})'.format(hostname))

        #set created for hosts that aren't new
        if not (h[1]['diff'] == "new"):
            outfile.write(' (created {0})'.format(hostname))
            if hostObject.getNameApplied():
                outfile.write(' (named {0})'.format(hostname))
        else:
            outfile.write(' (new {0})'.format(hostname))

        #only diff for hosts which haven't been removed 
        if (h[1]['diff'] == "changed") or (h[1]['diff'] == "unchanged"):
            #check all attributes in the diff
            if h[1]['cpus']['diff'] == "unchanged":
                outfile.write(' (cpusConfigured {0})'.format(hostname))
            if (h[1]['memoryMin']['diff'] == "unchanged") and (h[1]['memoryMax']['diff'] == "unchanged"):
                outfile.write(' (memoryConfigured {0})'.format(hostname))
            if not h[1]['templates']['diff'] == "unchanged":
                outfile.write(' (templateChanged {0})'.format(hostname))

            #check routing
            if getPddlType(hostObject.getTemplate()) == "router":
                if "routes" in h[1]:
                    if h[1]['routes']['diff'] == "unchanged":
                        outfile.write('\n\t\t(routingConfigured {0})'.format(hostname))
                else:   #hosts that don't list routing at all haven't changed in that regard
                    outfile.write('\n\t\t(routingConfigured {0})'.format(hostname))

        elif h[1]['diff'] == "removed":
            outfile.write(' (old {0})'.format(hostname))


        if "firewallrules" in h[1]:
            if h[1]['firewallrules']['diff'] == "unchanged":
                outfile.write('\n\t\t(firewallConfigured {0})'.format(hostname))
        else:   #hosts that don't list firewalls at all haven't changed in that regard
            outfile.write('\n\t\t(firewallConfigured {0})'.format(hostname))

        #specify part-of relationships with associated disks and set predicates for all disks
        if "disks" in h[1]:
            for d in h[1]['disks']['elements']:
                outfile.write('\n\t\t(part-of {0} {1})'.format(d[0], hostname))
                writeInitDisk(outfile, d, state)

        #specify part-of relationships with associated interfaces and set predicates for all interfaces
        if "interfaces" in h[1]:
            for i in h[1]['interfaces']['elements']:
                outfile.write('\n\t\t(part-of {0} {1})'.format(i[0], hostname))
                writeInitInterface(outfile, i, state)

def writeInitDisk(outfile, diskDiff, state):
    """
    Specify the initial state of a disk in the new configuration file, 
    depending on how it has changed compared to the old config (diff)

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        diskDiff -- dictionary listing all properties that changed between the old and the new configuration for this interface specifically
        state -- All objects associated with their name
    """
    diskName = diskDiff[0]
    diskObject = state[diskName] #state

    #we do not diff on size in a sense that disks are resized in the planner
    if (not diskDiff[1]['diff'] == "new") or (diskObject.getID() == diskObject.getHost().getDefaultDiskName()):
        outfile.write(' (attached {0} {1})'.format(diskName, diskObject.getHost().getID()))
    else:
        outfile.write(' (new {0})'.format(diskName))
    
    if diskDiff[1]['diff'] == "removed":
        outfile.write(' (old {0})'.format(diskName))

def writeInitInterface(outfile, ifaceDiff, state):
    """
    Specify the initial state of an interfaces in the new configuration file, 
    depending on how it has changed compared to the old config (diff)

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        ifaceDiff -- dictionary listing all properties that changed between the old and the new configuration for this interface specifically
        state -- All objects associated with their name
    """
    interfaceName = ifaceDiff[0]
    interfaceObject = state[interfaceName] #state

    #specifiy the part-of relationship with their network
    outfile.write('\n\t\t(part-of {0} {1})'.format(interfaceName, interfaceObject.getNetwork().getGlobalID()))

    #write static property if all IPs of the interface are static
    if len(interfaceObject.getAddresses()) > 0 and all(ip.getStatic() for ip in interfaceObject.getAddresses()):
        outfile.write('\n\t\t(static {0})'.format(interfaceName))

    #set created for interfaces that aren't new
    if not ifaceDiff[1]['diff'] == "new":
        outfile.write(' (created {0})'.format(interfaceName))
    
    #only diff for interfaces which have change (not new or removed)
    if (ifaceDiff[1]['diff'] == "changed") or (ifaceDiff[1]['diff'] == "unchanged"):
        #check all attributes in the diff, 'hardware' changes, no effect on interfaceConfigured on Host
        if ifaceDiff[1]['networkId']['diff'] == "unchanged":
            outfile.write(' (networkConfigured {0})'.format(interfaceName))
        if ifaceDiff[1]['mtu']['diff'] == "unchanged":
            outfile.write(' (mtuConfigured {0})'.format(interfaceName))
        if ifaceDiff[1]['rate']['diff'] == "unchanged":
            outfile.write(' (rateConfigured {0})'.format(interfaceName))
        
        #interface can be considered configured if nothing has changed and layer3addresses are not new/removed
        if 'layer3addresses' in ifaceDiff[1]:
            ips = ifaceDiff[1]['layer3addresses']['elements']

            #unchanged addresses or DHCP interfaces that only have been removed are considered to be configured correctly 
            if (ifaceDiff[1]['layer3addresses']['diff'] == "unchanged") or ((ifaceDiff[1]['layer3addresses']['diff'] == "removed") and all(not state[i[0]].getStatic() for i in ips)) or ((ifaceDiff[1]['layer3addresses']['diff'] == "new") and all(not state[i[0]].getStatic() for i in ips)):
                outfile.write(' (interfaceConfigured {0})'.format(interfaceName))
            else:   #otherwise, there is still the possibility of configuredInterfaces if only services have changed and gateway/netmask are unchanged
                if all(((not 'gateway' in ip[1]) or (ip[1]['gateway']['diff'] == "unchanged")) and ((not 'netmask' in ip[1]) or (ip[1]['netmask']['diff'] == "unchanged")) for ip in ips) and all(not (ip[1]['diff'] == "removed") or (not state[ip[0]].getStatic()) for ip in ips):
                    outfile.write(' (interfaceConfigured {0})'.format(interfaceName))
        else:
            outfile.write(' (interfaceConfigured {0})'.format(interfaceName))

    elif ifaceDiff[1]['diff'] == "removed":
        outfile.write(' (old {0})'.format(interfaceName))
          
    #set predicates for all basic services (dns/dhcp)
    if 'layer3addresses' in ifaceDiff[1]:
        for ip in ifaceDiff[1]['layer3addresses']['elements']:
            if 'dhcpservices' in ip[1]:
                for dhcp in ip[1]['dhcpservices']['elements']:
                    writeInitDhcpService(outfile, dhcp, state)
            if 'dnsservices' in ip[1]:
                for dns in ip[1]['dnsservices']['elements']:
                    writeInitDnsService(outfile, dns, state)
            #todo: handle common services, subclasses cannot be handled generically.

def writeInitDhcpService(outfile, dhcpDiff, state):
    """
    Specify the initial state a DHCP service in the new configuration file, 
    depending on how it has changed compared to the old config (diff)

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        iface -- dictionary listing all properties that changed between 
                the old and the new configuration for this interface specifically
        state -- All objects associated with their name
    """
    #write part-of, regardless of diff value
    dhcpObject = state[dhcpDiff[0]]
    outfile.write('\n\t\t(part-of {0} {1})'.format(dhcpDiff[0], dhcpObject.getInterface().getGlobalID()))

    if dhcpDiff[1]['diff'] == "unchanged":
        outfile.write(' (dhcpConfigured {0})'.format(dhcpDiff[0]))
    elif dhcpDiff[1]['diff'] == "removed":
        outfile.write(' (old {0})'.format(dhcpDiff[0]))

def writeInitDnsService(outfile, dnsDiff, state):
    """
    Specify the initial state a DHCP service in the new configuration file, 
    depending on how it has changed compared to the old config (diff)

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        iface -- dictionary listing all properties that changed between 
                the old and the new configuration for this interface specifically
        state -- All objects associated with their name
    """ 
    #write part-of, regardless of diff value
    dnsObject = state[dnsDiff[0]]
    outfile.write('\n\t\t(part-of {0} {1})'.format(dnsDiff[0], dnsObject.getInterface().getGlobalID()))
    
    if dnsDiff[1]['diff'] == "new":
        outfile.write(' (new {0})'.format(dnsDiff[0]))
    elif dnsDiff[1]['diff'] == "unchanged":
        outfile.write(' (dnsConfigured {0})'.format(dnsDiff[0]))
    elif dnsDiff[1]['diff'] == "removed":
        outfile.write(' (old {0})'.format(dnsDiff[0]))

def writeInitNetworks(outfile, diff, state):
    """
    Specify the initial state of all networks in the new configuration file, 
    depending on how they have changed compared to the old config (diff)

    Keyword arguments:
        outfile -- file handle pointing to the problem file
        diff -- dictionary listing all properties that changed between 
                the old and the new configuration for each object
        state -- All objects associated with their name
    """

    for n in diff['l2networks']:
        netname = n[0]

        #set created for networks that aren't removed or new
        if not n[1]['diff'] == "new":
            outfile.write('\n\t\t(created {0})'.format(netname))
        else:
            outfile.write(' (new {0})'.format(netname))

        if n[1]['diff'] == "removed":
            outfile.write(' (old {0})'.format(netname))


def writeGoal(outfile):
    """
    Write the fixed goal of the PDDL problem for all components of the config.

    Keyword arguments:
        outfile -- file handle pointing to the problem file
    """
    #Set the goal
    outfile.write('\t(:goal\n')
    outfile.write('\t\t(and\n')
    
    #write fixed part like "all networks have to be created", "all hosts have to be named and have their interfaces configured" ...
    outfile.write('\t\t\t(forall (?x) (imply (old ?x) (not (created ?x))))\n')
    outfile.write('\t\t\t(forall (?n - network) (imply (not (old ?n)) (created ?n)))\n')
    outfile.write('\t\t\t(forall (?h - host) (imply (not (old ?h)) (and (running ?h) (named ?h) (not (templateChanged ?h)) (cpusConfigured ?h) (memoryConfigured ?h) (firewallConfigured ?h) (not (nameNotApplied ?h)))))\n')
    outfile.write('\t\t\t(forall (?i - interface) (imply (not (old ?i)) (and (created ?i) (rateConfigured ?i) (mtuConfigured ?i) (networkConfigured ?i) (interfaceConfigured ?i))))\n')
    outfile.write('\t\t\t(forall (?d - dns) (dnsConfigured ?d))\n')
    outfile.write('\t\t\t(forall (?d - dhcp) (dhcpConfigured ?d))\n')
    outfile.write('\t\t\t(forall (?r - router) (routingConfigured ?r))\n')

    outfile.write('\t\t\t(forall (?x - interface) (imply (old ?x) (not (interfaceConfigured ?x))))\n')
    outfile.write('\t\t\t(forall (?x - network) (imply (new ?x) (configNameAdded ?x)))\n')
    outfile.write('\t\t\t(forall (?x - host) (imply (new ?x) (configNameAdded ?x)))\n')
    outfile.write('\t\t\t(forall (?x - disk) (imply (new ?x) (configNameAdded ?x)))\n')
    outfile.write('\t\t\t(forall (?h - host) (forall (?d - disk) (imply (and (part-of ?d ?h) (not (old ?d))) (attached ?d ?h))))\n')
    outfile.write('\t\t\t(forall (?h - host) (forall (?d - disk) (imply (and (part-of ?d ?h) (old ?d)) (not (attached ?d ?h)))))\n')

    outfile.write('\t\t)\n') #closing brace for (and)
    outfile.write('\t)\n') #closing brace for (:goal)

    #optional metric
    outfile.write('\t(:metric minimize (total-cost))\n')


def getObjectDict(oldConfig, newConfig):
    """
    Creates a dictionary containing all elements of a plan associated with their name.

    Keyword arguments:
        oldConfig -- Configuration representing current (or 'old') testbed state
        newConfig -- Configuration representing new testbed state
    """
    objects = {}
    #new objects
    for n in newConfig.getL2Networks():
        objects[n.getGlobalID().lower()] = n
    for h in newConfig.getHosts():
        objects[h.getGlobalID().lower()] = h
        for d in h.getDisks():
            if not d.getGlobalID().lower() in objects:
                objects[d.getGlobalID().lower()] = d
        for i in h.getInterfaces():
            objects[i.getGlobalID().lower()] = i
            #get services
            for ip in i.getAddresses():
                objects[ip.getGlobalID().lower()] = ip
                for s in ip.getAllNeighbors(type=DhcpService):
                    objects[s.getGlobalID().lower()] = s
                for s in ip.getAllNeighbors(type=DnsService):
                    objects[s.getGlobalID().lower()] = s

    #removed objects
    for n in oldConfig.getL2Networks():
        if not n.getGlobalID().lower() in objects:
            objects[n.getGlobalID().lower()] = n

    for h in oldConfig.getHosts():
        if not h.getGlobalID().lower() in objects:
            objects[h.getGlobalID().lower()] = h
        for d in h.getDisks():
            if not d.getGlobalID().lower() in objects:
                objects[d.getGlobalID().lower()] = d
        for i in h.getInterfaces():
            if not i.getGlobalID().lower() in objects:
                objects[i.getGlobalID().lower()] = i
            #get services
            for ip in i.getAddresses():
                objects[ip.getGlobalID().lower()] = ip
                for s in ip.getAllNeighbors(type=DhcpService):
                    if not s.getGlobalID().lower() in objects:
                        objects[s.getGlobalID().lower()] = s
                for s in ip.getAllNeighbors(type=DnsService):
                    if not s.getGlobalID().lower() in objects:
                        objects[s.getGlobalID().lower()] = s

    return objects

def getPddlType(template):
    """
    Find a suitable PDDL type for this template 

    :param template: Template to find a suitable PDDL type for
    :type template: insalata.model.Template.Template

    :returns: One of the types defined in the domain file for this problem domain.
    :rtype: str
    """
    if "router" in template.getMetadata():
        return "router"
    else:
        return "plain"  #todo: needs testing in case of host-base hosts that act as DHCP or DNS server
