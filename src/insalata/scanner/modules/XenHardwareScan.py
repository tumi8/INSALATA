from insalata import RpcConnection
from insalata.model.Host import Host
from insalata.model.Disk import Disk

def scan(graph, connectionInfo, logger, thread):
    """
    Get hardware information for each host in a Xen Environment.
    Method collects hardware data from XenServer.
    Updates will be stored in existing hosts.

    Necessary values in the configuration file of this collector module:
        - timeout   Timeout this collector module shall use (Integer)
        - xenuri    The URI opf the Xen server
        - xenuser   The username we use to connect to the Management API of the Xen server
        - xenpw     Password used for the connection
    
    :param graph: Data interface object for this collector module
    :type graph: insalata.model.Graph.Graph

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: logging:Logger

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """
    logger.info("Collecting hardware information from Xen")

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

    #Get required data from xen
    answer = xen.VM.get_all_records(session)
    if answer['Status'] == 'Failure':
        logger.error("Hardware scan on Xen server {0} failed. Server sent failure while reading all VMs.".format(connectionInfo['xenuri']))
        return
    hostRecords = answer['Value']

    answer = xen.VBD.get_all_records(session)
    if answer['Status'] == 'Failure':
        logger.error("Hardware scan on Xen server {0} failed. Server sent failure while reading all VBDs.".format(connectionInfo['xenuri']))
        return
    VBDRecords = answer['Value']

    answer = xen.VDI.get_all_records(session)
    if answer['Status'] == 'Failure':
        logger.error("Hardware scan on Xen server {0} failed. Server sent failure while reading all VDIs.".format(connectionInfo['xenuri']))
        return
    VDIRecords = answer['Value']

    #Insert data into graph
    for host in graph.getAllNeighbors(Host):
        logger.debug("Starting hardware scan on host: {0}".format(host.getID()))
        answer = xen.VM.get_by_name_label(session, host.getID())
        if answer['Status'] == 'Failure':
            logger.error("Hardware scan on Xen server {0} for host {1} failed. Server sent failure while getting record.".format(connectionInfo['xenuri'], host.getID()))
            continue
        if len(answer['Value']) == 0:
            logger.error("Hardware scan on Xen server {0} for host {1} failed. No record found for host.".format(connectionInfo['xenuri'], host.getID()))
        hostRecord = answer['Value'][0]

        host.setMemory(hostRecords[hostRecord]['memory_dynamic_min'], hostRecords[hostRecord]['memory_dynamic_max']) #RAM info
        host.setCPUs(hostRecords[hostRecord]['VCPUs_max']) #CPU info


        for host in graph.getAllNeighbors(Host):
            #Get Record for host
            answer = xen.VM.get_by_name_label(session, host.getID())
            if answer['Status'] == 'Failure':
                logger.error("Hardware scan on Xen server {0} for host {1} failed. Server sent failure while getting record for host.".format(connectionInfo['xenuri'], host.getID()))
                continue
            if len(answer['Value']) == 0:
                logger.error("Hardware scan on Xen server {0} for host {1} failed. No record found for host.".format(connectionInfo['xenuri'], host.getID()))
            hostRecord = answer['Value'][0]


            #Get a list of all vdis of the current host on the server
            nameToRecordDict = dict() #Disks on server
            for vbd in hostRecords[hostRecord]['VBDs']:
                if VBDRecords[vbd]['type'] == 'Disk' and VBDRecords[vbd]['VDI'] != "OpaqueRef:NULL":
                    name = VDIRecords[VBDRecords[vbd]['VDI']]['name_label']
                    nameToRecordDict[name] = VBDRecords[vbd]['VDI']
            deletedDisks = set()
            stillExistingDisks = set()
            for disk in host.getAllNeighbors(Disk):
                if disk.getID() in nameToRecordDict:
                    stillExistingDisks.add(disk)
                else:
                    disk.removeVerification(name)
                nameToRecordDict.pop(disk.getID()) #Determine which disks have to be created

            for diskName in list(nameToRecordDict.keys()): #Create new disks
                size = VDIRecords[nameToRecordDict[diskName]]['virtual_size']
                disk = graph.getOrCreateDisk(diskName, size, timeout, host, size=size)
                stillExistingDisks.add(disk)
                

            for disk in stillExistingDisks:
                disk.verify(name, timeout)
                host.addDisk(disk, name, timeout)

        #Get the VDIs on server which are not plugged
        nameToRecordDict = dict() #Disks on server
        for vdi in VDIRecords:
            if VDIRecords[vdi]['VBDs'] == []:
                nameToRecordDict[VDIRecords[vdi]['name_label']] = vdi
        
        currentDisks = set([disk for disk in graph.getAllNeighbors(Disk) if len(disk.getAllNeighbors(Host)) == 0]) #Current disks that are not plugged into a host
        deletedDisks = set()
        stillExistingDisks = set()
        for disk in currentDisks:
            if disk.getID() in list(nameToRecordDict.keys()):
                stillExistingDisks.add(disk)
            else:
                disk.removeVerification(name)
            nameToRecordDict.pop(disk.getID())

        for diskName in nameToRecordDict: #Create new disks 
            size = int(VDIRecords[nameToRecordDict[diskName]]['virtual_size'])
            disk = graph.getOrCreateDisk(diskName, name, timeout, host, size=size)
            stillExistingDisks.add(disk)

        for disk in stillExistingDisks:
            disk.verify(name, timeout)

    rpcConn.logout()