import json
import time
import nmap
import traceback
import socket
import subprocess
import sys
from insalata.builder.xenBuild.xenHelper import getXenConnection
from insalata.builder.decorator import builderFor
from insalata.builder.xenBuild.disk import insertConfigName as diskInsertConfigName
from insalata.builder.xenBuild.disk import findDisk as findDisk
from insalata.builder.xenBuild.disk import getConfigNames as getDiskConfigNames
from insalata.builder.xenBuild.disk import removeConfigName as diskRemoveConfigName

def findVM(host, logger, xen, session):
    """
    Find this host's reference in Xen (based on its ID). 

    :param host: Host-instance to find a Xen reference for.
    :type host: Host

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param xen: A xmlrpc reference to xen 
    :type xen: ServerProxy

    :param session: A session for the xen XML-RPC reference. 
    :type session: str

    :returns: A reference to the host in Xen if it exists, otherwise None.
    :rtype: str
    """
    request = xen.VM.get_by_name_label(session, host.getID())
    if "Value" in request and len(request['Value']) == 1:
        return request['Value'][0]
    else:
        logger.debug("VM named '" + host.getID() + "' not found.")
        return None

def getState(hostRef, logger, xen, session):
    """
    Get this host's current power state (halted, running, suspended)

    :param hostRef: A Xen reference to the host.
    :type hostRef: str

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param xen: A xmlrpc reference to xen 
    :type xen: ServerProxy

    :param session: A session for the xen XML-RPC reference. 
    :type session: str

    :returns: The host's power state
    :rtype: str
    """
    result = xen.VM.get_power_state(session, hostRef)
    if result['Status'] == 'Failure':
        logger.error("Error while getting power state of VM with reference '{0}'. Error: {1}.".format(hostRef, str(result['ErrorDescription'])))
        return None
    return result['Value']

@builderFor(action="createHost", hypervisor="xen")
def create(logger, host):
    """
    Create the given host in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to create.
    :type host: Host
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, storage = con

    ref = findVM(host, logger, xen, session)
    if ref:
        logger.warning("A machine named '{0}' exists already. Skipping creation.".format(host.getID()))
    else:
        #get the template
        result = xen.VM.get_by_name_label(session, host.getTemplate().getID())
        if result['Status'] == 'Failure':
            logger.error("Error while fetching the template named '{0}'. Error: {1}. Skipping creation.".format(host.getTemplate().getID(), str(result['ErrorDescription'])))
            return
        if len(result['Value']) == 0:
            logger.error("A template named '{0}' was not found. Skipping creation.".format(host.getTemplate().getID()))
            return
        
        template = result['Value'][0]
        logger.info("[{0}] Template found: {1}".format(host.getID(), host.getTemplate().getID()))

        #(full-)copy the specified template (cannot be parallelized!!!)
        logger.info("[{0}] Copy template as new machine: {1}".format(host.getID(), host.getID()))
        result = xen.VM.copy(session, template, host.getID(), storage)
        
        if result['Status'] == 'Failure':
            logger.warning("Error while cloning the template '{0}' for VM '{1}'. Error: {2}.".format(storage, host.getID(), str(result['ErrorDescription'])))
            return

        ref = result['Value']

        #Insert template name into other config
        xen.VM.add_to_other_config(session, ref, "template", host.getTemplate().getID())

        logger.info("[{0}] Copied template as new machine: {1}".format(host.getID(), host.getID()))

        #rename VDIs according to the name of the machine
        result = xen.VM.get_VBDs(session, ref)
        if result['Status'] == "Failure":
            logger.warning("Error while getting VBDs of new VM '{0}'. Error: {1}.".format(host.getID(), str(result['ErrorDescription'])))
            return

        #find vbd with type 'Disk'
        for vbd in result['Value']:
            result = xen.VBD.get_type(session, vbd)
            if result['Status'] == "Failure":
                logger.warning("Error while getting type of VBD of new VM '{0}'. Error: {1}.".format(host.getID(), str(result['ErrorDescription'])))
                return

            if result['Value'] == "Disk":
                result = xen.VBD.get_VDI(session, vbd)
                if result['Status'] == "Failure":
                    logger.warning("Error while getting a VDI of new VM '{0}'. Error: {1}.".format(host.getID(), str(result['ErrorDescription'])))
                    return
                vdi = result['Value']

                result = xen.VDI.set_name_label(session, vdi, host.getDefaultDiskName())
                if result['Status'] == "Failure":
                    logger.warning("Error while renaming the VDI of new VM '{0}' to '{1}'. Error: {2}.".format(host.getID(), host.getDefaultDiskName(), str(result['ErrorDescription'])))
                        
        #change description, which is still the template description
        xen.VM.set_name_description(session, ref, "Machine created by auto-config : " + time.strftime("%c"))
    
        configureMemory(logger, host)
        configureCPUs(logger, host)

        #set name not applied
        host.setNameApplied(False)

#Add a new config to the list of configs this machine is a member of
@builderFor(action="addConfigNameHost", hypervisor="xen")
def insertConfigName(logger, host, configId):
    """
    Add the given config identifier to the host's tags in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to modify.
    :type host: Host

    :param configId: An identifier for the configuration this host is now part of.
    :type configId: str
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    logger.info("Add configID {0} to host {1}.".format(configId, host.getID()))

    ref = findVM(host, logger, xen, session)
    if ref:
        otherConfig = xen.VM.get_other_config(session, ref)['Value']
        #get the current configs in the machine's 'other_config'
        configsArray = []
        if "configs" in otherConfig:
            configsArray = json.loads(otherConfig['configs'])
        #add the name of the config to the vm's list
        if not configId in configsArray:
            configsArray.append(configId)
        xen.VM.remove_from_other_config(session, ref, "configs")
        xen.VM.add_to_other_config(session, ref, "configs", json.dumps(configsArray))

        #also set other config of standard HDD
        disks = [d for d in host.getDisks() if d.getID() == host.getDefaultDiskName()]
        if len(disks) > 0:
            disk = disks[0] 
            diskInsertConfigName(logger, disk, configId)

#Remove a config from the list of configs in which this vm is a part of 
@builderFor(action="removeConfigNameHost", hypervisor="xen")
def removeConfigName(logger, host, configId):
    """
    Remove the given config identifier to the host's tags in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to modify.
    :type host: Host

    :param configId: An identifier for the configuration this host is removed from.
    :type configId: str
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    logger.info("Remove configID {0} from host {1}.".format(configId, host.getID()))

    ref = findVM(host, logger, xen, session)
    if ref:
        otherConfig = xen.VM.get_other_config(session, ref)['Value']
        if "configs" in otherConfig:
            configsArray = json.loads(otherConfig['configs'])
            if configId in configsArray:
                configsArray.remove(configId)
        xen.VM.remove_from_other_config(session, ref, "configs")
        xen.VM.add_to_other_config(session, ref, "configs", json.dumps(configsArray))

        #also set other config of standard HDD
        disks = [d for d in host.getDisks() if d.getID() == host.getDefaultDiskName()]
        if len(disks) > 0:
            disk = disks[0] 
            diskRemoveConfigName(logger, disk, configId)
        return configsArray

#Change memory
@builderFor(action="configureMemory", hypervisor="xen")
def configureMemory(logger, host):
    """
    Set the memory of the given host on the corresponding machine in Xen. 

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to modify.
    :type host: Host
    """
    xen, session, _ = getXenConnection(host.getLocation().getID(), logger)
    ref = findVM(host, logger, xen, session)
    if ref:
        #due to python integers being 64bit and xmlrpclib integers being 32bit, all specified integer params are actually Strings...
        (minMem, maxMem) = host.getMemory()
        result = xen.VM.set_memory_limits(session, ref, str(minMem), str(maxMem), str(minMem), str(maxMem))
        if result['Status'] == 'Failure':
            logger.error("[{0}] Memory set failed with error: {1}".format(host.getID(), str(result['ErrorDescription'])))
        else:
            logger.info("[{0}] Memory set: {1}-{2}".format(host.getID(), minMem, maxMem))

#Change number of VCPUs
@builderFor(action="configureCpus", hypervisor="xen")
def configureCPUs(logger, host):
    """
    Set the CPUs of the given host on the corresponding machine in Xen. 

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to modify.
    :type host: Host
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    ref = findVM(host, logger, xen, session)
    if ref:
        result1 = xen.VM.set_VCPUs_at_startup(session, ref, str(host.getCPUs()))
        result2 = xen.VM.set_VCPUs_max(session, ref, str(host.getCPUs()))

        if (result1['Status'] == 'Failure') or (result2['Status'] == 'Failure'):
            logger.error("[{0}] Setting VCPUs failed with error: {1} and {2}".format(host.getID(), str(result1['ErrorDescription']), str(result2['ErrorDescription'])))
        else: 
            logger.info("[{0}] VCPUs set: {1}".format(host.getID(), host.getCPUs()))

#Boot the vm
@builderFor(action="boot", hypervisor="xen")
def boot(logger, host):
    """
    Boot the machine corresponding to the host in Xen. 

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to boot.
    :type host: Host
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    ref = findVM(host, logger, xen, session)
    if ref:
        result = xen.VM.start(session, ref, False, False)
        if result['Status'] == 'Failure':
            logger.error("Error booting host " + host.getID() + ". Error: " + str(result['ErrorDescription']))
        else:
            waitForBoot(logger, host)
    else: 
        logger.error("Unable to boot host " + host.getID() + " as the host was not found in Xen.")

#Reboot the vm
@builderFor(action="reboot", hypervisor="xen")
def reboot(logger, host):
    """
    Reboot the machine corresponding to the host in Xen. 

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to reboot.
    :type host: Host
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    ref = findVM(host, logger, xen, session)
    if ref:
        result = xen.VM.clean_reboot(session, ref)
        if result['Status'] == 'Failure':
            logger.error("Error rebooting host " + host.getID() + ". Error: " + str(result['ErrorDescription']))
        else:
            waitForBoot(logger, host)
    else: 
        logger.error("Unable to reboot host " + host.getID() + " as the host was not found in Xen.")

def waitForBoot(logger, host):
    """
    Wait for a host to be booted in a sense that ssh is ready (using nmap)

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to wait for.
    :type host: Host
    """
    #find the correct name
    name = host.getID() if host.getNameApplied() else host.getTemplate().getID()

    #wait for the machine to be ssh-ready
    nm = nmap.PortScanner()

    logger.info("Boot VM {0}, waiting for SSH".format(name))

    isOffline = sshClosed = True 
    while isOffline or sshClosed:
        time.sleep(2)
        #scanres = nm.scan(name , '22', '')
        try:
            remoteServerIP = socket.gethostbyname(name)
        except Exception as e:
            logger.debug("Unable to resolve hostname '{}'".format(name))
            continue
        
        isOffline = False

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((remoteServerIP, 22))
        sock.close()
        if not result == 0: 
            continue
        else:
            sshClosed = False
            
    logger.info("Host '{0}' is reachable via SSH.".format(name))

        #scanres = {}
        #logger.info("SCANRES: " + scanres)
        #isOffline = scanres['nmap']['scanstats']['uphosts'] == '0'
        #if len(list(scanres['scan'].keys())) > 0:
        #    sshClosed = scanres['scan'][list(scanres['scan'].keys())[0]]['tcp'][22]['state'] == 'closed'
        #else:
        #    logger.info("VM {0} not up yet, keep waiting.".format(name))

#Clean shutdown of the vm
@builderFor(action="shutdown", hypervisor="xen")
def shutdown(logger, host):
    """
    Shutdown the machine corresponding to the host in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to shutdown.
    :type host: Host
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    ref = findVM(host, logger, xen, session)
    if ref:
        logger.info("Shutdown VM {0}".format(host.getID()))
        result = xen.VM.clean_shutdown(session, ref)
        if result['Status'] == 'Failure':
            logger.error("Error while shutting down " + host.getID() + ". Error: " + str(result['ErrorDescription']))
    else: 
        logger.error("Unable to shutdown host as the host was not found in Xen.")

#Remove a host from the xen server including its hard drive
@builderFor(action="removeHost", hypervisor="xen")
def destroy(logger, host):
    """
    Destroy the machine corresponding to the host on Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param host: Host-instance to destroy.
    :type host: Host
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    logger.info("Removal of host {0}.".format(host.getID()))

    ref = findVM(host, logger, xen, session)
    if ref:
        state = getState(ref, logger, xen, session)
        if not state == 'Halted':
            logger.error("The machine named {0} is not in halted state. Unable to delete.".format(host.getID()))
            return
    
        #delelete the VDIs and all VBDs using them
        #first, get the VDI
        for vdiObj in host.getDisks():
            vdiRef = findDisk(vdiObj, logger, xen, session)
                
            #find all VBDs and destroy each one
            vbdRequest = xen.VDI.get_VBDs(session, vdiRef)
            if not vbdRequest['Status'] == 'Failure':
                for vbd in vbdRequest['Value']:
                    xen.VBD.destroy(session, vbd)
            else:
                logger.warning("Problem while requesting VBDs of {0}. Error: {1}".format(host.getID(), vbdRequest['ErrorDescription']))

            #destroy the VDI if it isn't referenced anymore
            if len(getDiskConfigNames(xen, session, logger, vdiRef)) == 0:
                logger.info("Deleting VDI '{0}'.".format(vdiObj.getID()))
                xen.VDI.destroy(session, vdiRef)
            else:
                logger.info("VDI '{0}' not deleted, as it is still referenced in other configs.".format(vdiObj.getID()))

        #destroy the vm
        destroyRequest = xen.VM.destroy(session, ref)
        if destroyRequest['Status'] == 'Failure':
            logger.error("Error while deleting VM " + host.getID() + ". Error: " + str(destroyRequest['ErrorDescription']))
