import json
from insalata.builder.xenBuild.xenHelper import getXenConnection
from insalata.builder.decorator import builderFor

def findDisk(disk, logger, xen, session):
    """
    Find this disk's reference in Xen (based on its name). 

    :param interface: Disk to find a Xen reference for.
    :type interface: Disk
    
    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param xen: A xmlrpc reference to xen 
    :type xen: ServerProxy

    :param session: A session for the xen XML-RPC reference. 
    :type session: str

    :returns: A reference to the disk in Xen if it exists, otherwise None.
    :rtype: str
    """

    request = xen.VDI.get_by_name_label(session, disk.getID())
    if "Value" in request and len(request['Value']) == 1:
        return request['Value'][0]
    else:
        logger.info("VDI named '" + disk.getID() + "' not found.")
        return None


#Attach all disks if they can be found by name and aren't attached already
@builderFor(action="addDisk", hypervisor="xen")
def addDisk(logger, disk, host):
    """
    Add a Disk to the specified host if the disk exists, otherwise create it

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param disk: The disk to attach to the given host.
    :type disk: Disk

    :param host: The host to attach to the given host.
    :type host: Host
    """
    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, storage = con

    vmRef = findVM(host, logger, xen, session)

    if vmRef:
        vdisOfHost = getVDIsOfHost(host, logger)

        #add all disks specified as part of the VM
        for disk in host.getDisks():
            if not disk.getID() in [x[0] for x in vdisOfHost]: #add vdi
                #find the VDI and create it if it is not found
                vdiRef = findDisk(disk, logger, xen, session)

                if not vdiRef: #create
                    logger.debug("No VDI named '{0}' was found. Creating it instead.".format(disk.getID()))

                    #get SR for copy
                    result = xen.SR.get_by_name_label(session, storage)
                    if result['Status'] == 'Failure':
                        logger.error("Error while retrieving the storage named '{0}'. Error: {1}. Skipping creation.".format(storage, str(result['ErrorDescription'])))
                        return
                    if len(result['Value']) == 0:
                        logger.error("The storage named '{0}' was not found. Skipping creation.".format(storage))
                        return
                    
                    sr = result['Value'][0]
                    logger.info("Storage found: {1}".format(storage))
                    
                    result = xen.VDI.create({
                        "name_label": disk.getID(),
                        "SR": sr,
                        "virtual_size": disk.getSize(),
                        "type": "user",
                        "sharable": True,
                        "read_only": False,
                        "other_config": {}
                    })
                    if result['Status'] == 'Failure':
                        logger.error("Error while creating VDI named {0}. Error: {1}".format(disk.getID(), str(result['ErrorDescription'])))
                        return

                    vdiRef = result["Value"]

                #build vbd record
                vbdRecord = {
                    "type": "Disk",
                    "mode": "RW",
                    "bootable": False,
                    "unpluggable": False,
                    "qos_algorithm_type": "",
                    "qos_algorithm_params": {},
                    "empty": False,
                    "other_config": {},
                    "VDI": vdiRef,
                    "VM": vmRef,
                    "userdevice": "0" if vdisOfHost == [] else str(max(x[1] for x in vdisOfHost) + 1)
                }

                #create the VBD using the record above
                xen.VBD.create(session, vbdRecord)
                
                logger.info("Create VBD to add VDI {0} to VM {1}".format(disk.getID(), host.getID()))
                result = xen.VBD.create(session, vbdRecord)
                if result['Status'] == 'Failure':
                    logger.error("Error creating VBD for VDI {0} of VM {1]}. Error: {2}".format(disk.getID(), host.getID(), str(result['ErrorDescription'])))
                else:
                    xen.VBD.plug(result['Value'])
            else:
                logger.info("VDI '{0}' already attached to VM {1]}.".format(disk.getID(), host.getID()))


@builderFor(action="removeDisk", hypervisor="xen")
def removeDisk(logger, disk):
    """
    Destroy the given disk (VDI) in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param disk: Disk-instance to remove.
    :type disk: Disk
    """
    con = getXenConnection(disk.getHost().getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con
    
    ref = findDisk(disk, logger, xen, session)
    if ref:
        #find all VBDs and destroy each one
        vbdRequest = xen.VDI.get_VBDs(session, ref)
        if not vbdRequest['Status'] == 'Failure':
            for vbd in vbdRequest['Value']:
                xen.VBD.destroy(session, vbd)
        else:
            logger.warning("Problem while requesting VBDs of VDI {0}. Error: {1}".format(disk.getID(), vbdRequest['ErrorDescription']))

        #destroy the VDI
        destroyRequest = xen.VDI.destroy(session, ref)
        if destroyRequest['Status'] == 'Failure':
            logger.error("Error while deleting disk " + disk.getID() + ". Error: " + str(destroyRequest['ErrorDescription']))


#Add a new config to the list of configs this disk is a member of
@builderFor(action="addConfigNameDisk", hypervisor="xen")
def insertConfigName(logger, disk, configId):
    """
    Add the given config identifier to the disk's tags in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param disk: Disk-instance to modify.
    :type disk: Disk

    :param configId: An identifier for the configuration this disk is now part of.
    :type configId: str
    """

    con = getXenConnection(disk.getHost().getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    logger.info("Add configID {0} to disk {1}.".format(configId, disk.getID()))

    ref = findDisk(disk, logger, xen, session)
    if ref:
        configsArray = getConfigNames(xen, session, logger, ref)
        if not configId in configsArray:
            configsArray.append(configId)
            xen.VDI.remove_from_other_config(session, ref, "configs")
            xen.VDI.add_to_other_config(session, ref, "configs", json.dumps(configsArray))
    else:
        logger.warning("The VDI named '{0}' not found!".format(disk.getID()))

#Remove a config from the list of configs in which this disk is a part of
@builderFor(action="removeConfigNameDisk", hypervisor="xen") 
def removeConfigName(logger, disk, configId):
    """
    Remove the given config identifier to the disk's tags in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param disk: Disk-instance to modify.
    :type disk: Disk

    :param configId: An identifier for the configuration this disk is removed from.
    :type configId: str

    :returns: An array with the remaining config names that reference this disk after removal
    :rtype: [str]
    """

    con = getXenConnection(disk.getHost().getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    logger.info("Remove configID {0} from disk {1}.".format(configId, disk.getID()))

    ref = findDisk(disk, logger, xen, session)
    if ref:
        configsArray = getConfigNames(xen, session, logger, ref)
        if configId in configsArray:
            configsArray.remove(configId)
            xen.VDI.remove_from_other_config(session, ref, "configs")
            xen.VDI.add_to_other_config(session, ref, "configs", json.dumps(configsArray))
        return configsArray
    else:
        logger.warning("The VDI named '{0}' not found!".format(disk.getID()))
        return []

#Remove a config from the list of configs in which this disk is a part of
def getConfigNames(xen, session, logger, ref):
    """
    Return all config names associated with the given disk by reading the disk's other config in Xen.

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :param ref: Xen reference of the disk.
    :type ref: str

    :returns: An array with config names that reference this disk
    :rtype: [str]
    """

    result = xen.VDI.get_other_config(session, ref)
    if result['Status'] == "Failure":
        logger.warning("Error while getting other config of VDI. Error: {1}.".format(str(result['ErrorDescription'])))
        return
    otherConfig = result['Value']

    if "configs" in otherConfig:
        return json.loads(otherConfig['configs'])
    else:
        return []

def getVDIsOfHost(host, logger):
    """
    Get a list of all VDI names of VDIs attached to the given host (tuples associated with the VBD device no.)

    :param host: The host instance of the host to find all disks of.
    :type host: Host

    :param logger: A logger used for logging possible errors.
    :type logger: seealso:: :class:`logging:Logger`

    :returns: A list with VDI references from Xen
    :rtype: list(str)
    """

    con = getXenConnection(host.getLocation().getID(), logger)
    if not con:
        return
    xen, session, _ = con

    vm = findVM(host, logger, xen, session)

    #get a list of all disks currently attached to the VM
    result = xen.VM.get_VBDs(session, vm)
    if result['Status'] == "Failure":
        logger.warning("Error while getting VBDs of VM '{0}'. Error: {1}.".format(host.getID(), str(result['ErrorDescription'])))
        return

    vbdsInVM = result["Value"]
    vdisInVM = []
    for vbd in vbdsInVM:
        #get VBD's userdevice no.
        result = xen.VBD.get_record(session, vbd)
        if result['Status'] == "Failure":
            logger.warning("Error while getting a VBD information from VBD of VM '{0}'. Error: {1}.".format(host.getID(), str(result['ErrorDescription'])))
            return 

        userdevice = int(result['Value']['userdevice'])

        result = xen.VBD.get_VDI(session, vbd)
        if result['Status'] == "Failure":
            logger.warning("Error while getting a VDI of VM '{0}'. Error: {1}.".format(host.getID(), str(result['ErrorDescription'])))
            return
        
        vdi = result['Value']
        result = xen.VDI.get_name_label(session, vdi)
        if "Value" in result:
            vdisInVM.append((result["Value"], userdevice))

    return vdisInVM

from insalata.builder.xenBuild.host import findVM