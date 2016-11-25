from netaddr import IPNetwork, IPAddress

def isHostInNetwork(hostIp, netAddr, netmask):
    """
    Determines whether or not the given IP address of the host is part oyf the network specified by a network address and a subnetmask  
    
    :param hostIp: The IP of the host in decimal dotted notation
    :type hostIp: str

    :param netAddr: The network addresss in decimal dotted notation
    :type netAddr: str

    :param netmask: The netmask of the network in decimal dotted notation
    :type netmask: str
    """
    return IPAddress(hostIp) in IPNetwork(netAddr + "/" + str(getPrefix(netmask)))

def getNetAddress(ip, netmask):
    """
    Get the netaddress from an host ip and the netmask.

    :param ip: Hosts IP address
    :type ip: str

    :param netmask: Netmask of the network
    :type netmask: 
    
    :returns: Address of the network calculated using hostIP and netmask
    :rtype: str
    """
    return str(IPNetwork(ip + "/" + str(getPrefix(netmask))).network)


def getPrefix(netmask):
    """
    Get the CIDR prefix representing the netmask.

    :param netmask: Netmask to convert to CIDR
    :type netmask: 
    
    :returns: CIDR prefix representing the netmask
    :rtype: int
    """
    return sum([bin(int(x)).count('1') for x in netmask.split('.')])

def getIpAddress(ip, offset):
    """
    Get the IP adddress that is [offset] units before or after the given one.

    :param ip: IP address to start from.
    :type ip: str

    :param offset: Offset to add or remove from the IP address.
    :type offset: int

    :returns: New IP address.
    :rtype: str
    """
    return str(IPAddress(ip) + offset)

def getIpAddressDifference(ip1, ip2):
    """
    Get the number of IP addresses between two given IP addresses.

    :param ip1: The IP address acting as minuend.
    :type ip1: str

    :param ip1: The IP address acting as subtrahend.
    :type ip1: str

    :returns: The number of IP addresses between.
    :rtype: int
    """
    return int(IPAddress(ip1)) - int(IPAddress(ip2))

def getBroadcastAddress(netaddress, netmask):
    """
    Get the broadcast address of the given network as string.

    :param netaddress: The network's address
    :type netaddress: str

    :param netmask: The netmask of the given network.
    :type netmask: str

    :returns: The broadcast address.
    :rtype: str
    """
    return str(IPNetwork(netaddress + "/" + str(getPrefix(netmask))).broadcast)