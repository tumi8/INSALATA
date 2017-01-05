from insalata.helper.SSHWrapper import SSHWrapper
import re
import subprocess
from insalata.model.Layer3Address import Layer3Address

def scan(graph, connectionInfo, logger, thread):
    """
    Detect network components using tcpdump.
    We will only add addresses as Hosts to the the Graph, if there is no Layer3Address with the same ID!

    Necessary values in the configuration file of this collector module:
        - timeout           Timeout this collector module shall use (Integer)
        - monitoringServer  The network component we want to start tcpdump on.
                            If the device is localhost, no ssh connection is used.
                            If the monitoring server != localhost, we will establish an ssh connection
    
    :param graph: Data interface object for this collector module
    :type graph: insalata.model.Graph.Graph

    :param connectionInfo: Information needed to connect to xen server
    :type connectionInfo: dict

    :param logger: The logger this scanner shall use
    :type logger: logging:Logger

    :param thread: Thread executing this collector
    :type thread: insalata.scanner.Worker.Worker
    """

    name = connectionInfo["name"]
    timeout = int(connectionInfo["timeout"])
    monServer = connectionInfo["monitoringServer"]
    logger.debug("Starting host scan using tcpdump on monitoring server {0}".format(monServer))

    if monServer != "localhost":
        ssh = SSHWrapper()
        ssh.connect(monServer) # TODO no connection possible
        stdout = ssh.executeTcpdump("-i any host not localhost and not arp and not rarp")
    else:
        proc = subprocess.Popen("tcpdump -i any host not localhost and not arp and not rarp and not ip6".split(" "), stdout=subprocess.PIPE)
        stdout = proc.stdout

    while(thread.stopRequested):
        packet = stdout.readline()
        if isinstance(packet, bytes):
            packet = packet.decode("ascii")
        #logger.debug(packet)
        # Start ssh connection and read output line by line
        res = re.search(r"[0-9\:\.]+([^,]+,)? IP ([^ ]+) >", packet)
        if not res:
            continue
        res = res.group(2)

        # We know that the src host exists in the network
        src = ".".join(res.split(".")[:4])
        #logger.debug("Found host in physical environment: {0}".format(src))
        #logger.debug(packet)

        location = graph.getOrCreateLocation("physical", name, timeout)

        if len([a for a in graph.getAllNeighbors(Layer3Address) if a.getID() == src]) == 0:
            host = graph.getOrCreateHost(src, name, timeout, location=location)
            host.setLocation(location)
            logger.debug("Tcpdump: Added host to graph: {}".format(host.getID()))

    ssh.close()