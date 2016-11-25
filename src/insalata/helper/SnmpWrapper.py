from pysnmp.hlapi import *
from enum import Enum
from pysnmp.error import PySnmpError
from pysnmp.entity.rfc3413.oneliner import cmdgen
import string
import ipaddress

Values = {
    "hostForwarding" : "1.3.6.1.2.1.4.1.0",
    "destRoute" : "1.3.6.1.2.1.4.24.4.1.1",
    "netmask" : "1.3.6.1.2.1.4.24.4.1.2",
    "nextHop" : "1.3.6.1.2.1.4.24.4.1.4",
    "interfaceIndex" : "1.3.6.1.2.1.4.24.4.1.5",
    "mac" : "1.3.6.1.2.1.2.2.1.6"
}

class SnmpWrapper:

    def __init__(self, host, user, passwordMD5, passwordDES, port=161):
        """
        Create a new snmp connection wrapper for a host.
        This wrapper uses SNMPv3 with MD for authentification and DES for encryption.

        :param host: Host or IP to connect to
        :param host: str

        :param port: Port used for the snmp connection
        :type port: int

        :param user: User used for the snmp connection
        :type user: str

        :param passwordMD5: Password used for snmp authentifications
        :type passwordMD5: str

        :param passwordDES: Password used for snmp encryption
        :type: str
        """
        self.user = user
        self.auth = passwordMD5
        self.enc = passwordDES
        self.host = host
        self.port = port

    def getValue(self, oid, number=None):
        """
        Execute a GET command on the host defined in the constructor.

        :param oid: Value/OID to receive from the host
        :type oid: str

        :param number: Subelement of given OID if needed. For example interface if you want to read ips
        :type number: int 

        :returns: Value returned by the SNMP-Agent or error code.
            0 : Unknown error
            1 : Connection-Timeout: Host has no installed SNMP-Agent or encryption password is wrong.
            2 : Authentification failed due to wrong authentification password.
            3 : Unknown username
            4 : Host not reachable
        :rtype: tuple on success, int on error
        """
        if number:
            oid += "." + str(number)

        try:
            errorIndication, errorStatus, errorIndex, varBinds = next(
                                                                    getCmd(SnmpEngine(),
                                                                        UsmUserData(self.user, self.auth, self.enc),
                                                                        UdpTransportTarget((self.host, self.port)),
                                                                        ContextData(),
                                                                        ObjectType(ObjectIdentity(oid)))
            )
        except PySnmpError:
            return 4

        if errorIndication:
            if errorIndication == "No SNMP response received before timeout":
                return 1
            if errorIndication == "wrongDigest":
                return 2
            if errorIndication == "unknownUserName":
                return 3
            return 0
        elif errorStatus or errorIndex != 0:
            return 0
        else:
            if len(varBinds) > 0:
                return (str(varBinds[0][0]), toPythonType(varBinds[0][1]))
            return None


    def walkOid(self, oid):
        """
        Execute a GETNEXT command on the host defined in the constructor.
        Method will return all values which are subidentifiers of the fiven one.

        :param oid: Value/OID to receive from the host
        :type oid: str

        :param number: Subelement of given OID if needed. For example interface if you want to read ips
        :type number: int

        :returns: List of values returned by the SNMP-Agent or error code.
            0 : Unknown error
            1 : Connection-Timeout: Host has no installed SNMP-Agent or encryption password is wrong.
            2 : Authentification failed due to wrong authentification password.
            3 : Unknown username
            4 : Host not reachable
        :rtype: list on success, int on error
        """
        try:
            cmd = nextCmd(SnmpEngine(),
                UsmUserData(self.user, self.auth, self.enc),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode = False)

            vars = list()
            for errorIndication, errorStatus, errorIndex, varBinds in cmd:
                if errorIndication:
                    if errorIndication == "No SNMP response received before timeout":
                        return 1
                    if errorIndication == "wrongDigest":
                        return 2
                    if errorIndication == "unknownUserName":
                        return 3
                    return 0
                elif errorStatus or errorIndex != 0:
                    return 0
                else:
                    for oid, value in varBinds:
                        vars.append((str(oid), toPythonType(value)))

            return vars
        except PySnmpError:
            return 4

def OidToRouteIdentifier(oid):
    """
    Generate the subidentifier for one route.
    The oid has the schema: <oid>.<4 dot seperated values dest-network>.<4 dot seperated values netmask>.<4 dot seperated values hop>

    :param oid: OID to split
    :type oid: str

    :returns: sub-oid representing the route (Without leading dot)
    :rtype: str
    """
    parts = oid.rsplit(".", 13)
    return ".".join(parts[1:])

def toPythonType(value):
    if isinstance(value, Integer32) or isinstance(value, Integer) or isinstance(value, Gauge32) or isinstance(value, Counter32) or isinstance(value, Counter64) or isinstance(value, Unsigned32):
        return int(value)
    if isinstance(value, IpAddress):
        return ".".join([str(c) for c in value._value])
    if isinstance(value, ObjectIdentifier):
        return str(value)
    if isinstance(value, OctetString) and isinstance(value._value, bytes):
        return value
    if isinstance(value, OctetString):
        return str(value)
    return value

def checkReturnSnmp(answer, host, name, user, logger):
    """
    Check the return type of SnmpWrapper functions and log if an error occured.

    :param answer: Answer received from SnmapWrapper method
    :type answer: list, tuple or int

    :param host: Host currently processed
    :type host: seealso: insalata.model.Host.Host

    :param name: Name of this collector
    :type name: str

    :param user: User used for SNMP connection
    :type user: str

    :param logger: Logger used by this collector module
    :type logger: seealso: insalata.Logging.Logger

    :returns: answer if no error occured else None
    :rtype: list, tuple or None
    """
    if isinstance(answer, list) or isinstance(answer, tuple) or isinstance(answer, int) or isinstance(answer, string) or isinstance(answer, bytes):
        return answer

    if len(answer) == 1:
        logger.error("Host '{0}' does not support SNMP or encryption password is wrong. Collector: {1}.".format(host.getID(), name))
    if len(answer) == 2:
        logger.error("Authentification failed on host '{0}'. Collector: {1}.".format(host.getID(), name))
    if len(answer) == 3:
        logger.error("Unknown SNMP user on host '{0}'. Collector: {1}. Username: {3}.".format(host.getID(), name, user))
    if len(answer) == 4:
        logger.error("Host '{0}' is not reachable. Collector: {1}.".format(host.getID(), name))
    if len(answer) > 4:
        logger.error("SNMP scanning of host '{0}' failed due to unknown reason. Collector: {1}.".format(host.getID(), name))
        logger.debug("SNMP scanning of host '{0}' failed due to unknown reason. Collector: {1}; Anser-Code: {2}.".format(host.getID(), name, answer))
    return None