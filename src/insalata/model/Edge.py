from insalata.Timer import Timer
import datetime

class Edge:
    def __init__(self, first, second, collectorName=None, timeout=None, association=None, changed=None, name=None):
        """
        Create a new edge between node 'first' and node 'second'.

        :param first: First node incident to this edge
        :type first: insalata.model.Node.Node

        :param second: Second node incident to this edge
        :type second: insalata.model.Node.Node

        :param collectorName: (optional) Scanner that verifies this edge
        :type collectorName: str

        :param timeout: (optional) Timeout of verifycation
        :type timeout: int

        :param association: Name of the association this edge is representing. 
                            Used by setters for onChange
        :type association: str

        :param changed: Changed element (Used for OnChange)
        :type changed: insalata.model.Node.Node
        """
        if first.getDeprecated() or second.getDeprecated():
            raise BaseException("Node depricated.")
        self.__nodes = (first, second)
        first.addEdge(self)
        second.addEdge(self)

        self.__scanners = dict() #List of Timers
        self.__lifetimeStart = datetime.datetime.now()
        self.__lifetimeEnd = None

        self.__name = None
        if name:
            self.__name = name

        self.verify(collectorName, timeout)

        self.callOnChange(first, second, "add", association, changed)

    def getName(self):
        return self.__name

    def callOnChange(self, first, second, mode, association=None, changed=None):
        """
        Call the correct OnChangeEvent of the node(s).

        :param first: First node incident to this edge
        :type first: insalata.model.Node.Node

        :param second: Second node incident to this edge
        :type second: insalata.model.Node.Node

        :param mode: add or delete
        :type mode: str

        :param association: Name of the association this edge is representing. 
                            Used by setters for onChange
        :type association: str

        :param changed: Changed element (Used for OnChange)
        :type changed: insalata.model.Node.Node
        """
        args = {
            "type" : mode,
        }
        if association:
            args["member"] = association

        if changed:
            other = self.getOther(changed)
            args["value"] = other.getGlobalID()
            changed.getOnChangeEvent().trigger(changed, args)
        else:
            args["value"] = second.getGlobalID()
            first.getOnChangeEvent().trigger(first, args)

            args["value"] = first.getGlobalID()
            second.getOnChangeEvent().trigger(second, args)


    def delete(self, association=None, changed=None):
        """
        Delete this edge and remove its entry in all incident nodes.

        :param association: Name of the association this edge is representing. 
                            Used by setters for onChange
        :type association: str

        :param changed: Changed element (Used for OnChange)
        :type changed: insalata.model.Node.Node
        """
        self.__lifetimeEnd = datetime.datetime.now()
        self.callOnChange(self.__nodes[0], self.__nodes[1], "delete", association, changed)
        for node in self.__nodes:
            node.removeEdge(self)
        for timer in list(self.getScanners().keys()):
            self.getScanners()[timer].cancel()

    def getScanners(self):
        """
        Get all timers of this node.
        """
        return self.__scanners

    def getNodes(self):
        """
        Return the two node objects of this edge.

        Returns:
            Tuple with both nodes that are connected by this edge.
        """
        return self.__nodes

    def getOther(self, node):
        """
        Return the node that is incident to this edge which is not equal to the given node object.

        Keyword arguments:
            node -- One of the nodes that are incident to this edge. The other one will be returned.

        Returns:
            Node object -- Node that is incident to this edge and is not equal to the given one
                Method will return None if node does not match one of the incident nodes.
        """
        first, second = self.__nodes
        return first if second == node else second


        
    def verify(self, collectorName, timeout):
        """
        Verify this edge and start the timer.

        Keyword arguments:
            collectorName -- Name of the scanner that verifies this edge.
            timeout -- Timeout in seconds. After this timeout the scanner will be deleted from the list of verifying scanners.
        """
        if (collectorName is not None) and (timeout is not None):
            if collectorName in self.__scanners:
                self.getScanners()[collectorName].cancel()
            self.getScanners()[collectorName] = Timer(timeout, self.removeVerification, [collectorName])
            self.getScanners()[collectorName].start()


    def removeVerification(self, collectorName):
        """
        Remove a scanner from the list of scanners that verify this object.
        If no scanner verifies this edge, it will be deleted.

        Keyword arguments:
            collectorName -- Scanner to remove.
        """
        if collectorName in list(self.getScanners().keys()):
            self.getScanners()[collectorName].cancel()
            self.getScanners().pop(collectorName, None)
        if len(self.getScanners()) == 0:
            self.delete()

    def getTimers(self):
        """
        Return all verification Timers of this edge.
        """
        return self.__scanners.values()