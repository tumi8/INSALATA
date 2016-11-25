import datetime
from random import randint

from insalata.model.Event import Event
from insalata.Timer import Timer


class Node:
    def __init__(self, collectorName=None, timeout=None):
        """
        Create anew node in the graph.

        :param collectorName: (optional) Scanner that verifies this node
        :type collectorName: str

        :param timeout: (optional) Timeout of verifycation
        :type timeout: int
        """
        self.__edges = set()
        self.__scanners = dict() #List of Timers
        self.__lifetimeStart = datetime.datetime.now()
        self.__lifetimeEnd = None
        self.__bfsRand = None
        self.__deprecated = False #Flag that shows if this Node is valid -> If True: It is not allowed to create a Edge to this Node

        self.__onChangeEvent = Event()
        self.__onDeleteEvent = Event()

        self.verify(collectorName, timeout)

    def getTimers(self):
        """
        Return all verification Timers of this node.
        """
        return self.__scanners.values()

    def getOnChangeEvent(self):
        """
        Return the onChangeEvent of this node.

        The onChangeEvent is triggered everytime a value is changed.
        """
        return self.__onChangeEvent

    def getOnDeleteEvent(self):
        """
        Return the onDeleteEvent of this node.

        The objectDeletedEvent is triggered when the object is deleted.
        """
        return self.__onDeleteEvent

    def delete(self):
        """
        Delete this node and all edges pointing to it.

        Triggers the onDeleteEvent.
        """
        self.__deprecated = True
        self.__lifetimeEnd = datetime.datetime.now()
        for edge in self.getEdges():
            edge.delete()
        for timer in list(self.getScanners().keys()):
            self.getScanners()[timer].cancel()

        self.getOnDeleteEvent().trigger(self, {})

    def getDeprecated(self):
        return self.__deprecated


    def getScanners(self):
        """
        Get all timers of this node.
        """
        return self.__scanners
        
    def addEdge(self, edge):
        """
        Add an edge to the set of edges of this node object.

        :param edge: Edge which should be added to the set of edges
        :type edge: insalata.model.Edge.Edge
        """
        self.__edges.add(edge)

    def removeEdge(self, edge):
        """
        Remove an edge from the list of edges of this node object.

         :param edge: Edge which should be removed from the set of edges
         :type edge: insalata.model.Edge.Edge
        """
        try:
            self.__edges.remove(edge)
        except: #Ignore if edge is not part of the edges set
            pass

   
    def getEdges(self):
        """
        Return the set of all edges of this node object.

        Returns:
            set of all edges.
        """
        return frozenset(self.__edges)


    
    def getAllNeighbors(self, type=None):
        """
        Get all neighbors of this node of a special type.

        Keyword arguments:
            type -- Type of the returned objects. If None all neighbors will be returned.

        Returns:
            set of all neighbors of the type.
        """
        neighbors = set()
        for e in self.getEdges():
            neighbor = e.getOther(self)
            if (type is None) or isinstance(neighbor, type):
                neighbors.add(neighbor)

        return frozenset(neighbors)

        
    def verify(self, collectorName, timeout):
        """
        Verify this node and start the timer.

        :param collectorName: Name of the scanner that verifies this node
        :type collectorName: str

        :param timeout: Timeout in seconds. After this timeout the scanner will be deleted from the list of verifying scanners
        :type timeout: int
        """
        if (collectorName is not None) and (timeout is not None):
            if collectorName in list(self.getScanners().keys()):
                self.getScanners()[collectorName].cancel()
            self.getScanners()[collectorName] = Timer(timeout, self.removeVerificationTimeout, [collectorName])
            self.getScanners()[collectorName].start()

    def removeVerification(self, collectorName):
        """
        Remove a scanner from the list of scanners that verify this object.
        If no scanner verifies this node, he will be deleted.

        :param collecorName: Scanner to remove
        :type collectorName: str
        """
        if collectorName in list(self.getScanners()):
            self.getScanners().pop(collectorName, None)
            self.getScanners()[collectorName].cancel()
        if len(self.getScanners()) == 0:
            self.delete()

    def removeVerificationTimeout(self, collectorName):
        if collectorName in list(self.getScanners()):
            self.getScanners().pop(collectorName, None)
        if len(self.getScanners()) == 0:
            self.delete()

    def bfs(self, action):
        action(self)
        return self.getAllNeighbors()

    def toGraphViz(self):
        colors = {
            "Host" : "cyan",
            "Layer2Network" : "darkorange1",
            "Interface" : "darkolivegreen1",
            "Location" : "goldenrod",
            "Route" : "chartreuse2",
            "Layer3Address" : "chocolate3",
            "Service" : "bisque3",
            "DnsService" : "bisque3",
            "DhcpService" : "bisque3",
            "Disk" : "antiquewhite3",
            "Layer3Network" : "hotpink",
            "FirewallRule" : "firebrick1",
            "FirewallRaw" : "firebrick1",
            "Template" : "cornsilk1"
        }
        if self.__class__.__name__ == "Graph":
            return
        print(self.getBfsID() + " [style=filled, fillcolor={0}];".format(colors[self.__class__.__name__]))
        for edge in self.getEdges():
            #if not (edge.getOther(self).__class__.__name__ == "Graph"):
            print(self.getBfsID() + ' -> ' + edge.getOther(self).getBfsID() + ";")

        
    def getBfsID(self):
        if hasattr(self, 'getGlobalID'):
            return '"' + self.getGlobalID() + '"'
        else:
            if self.__bfsRand is None:
                self.__bfsRand = str(randint(0, 10000))
            return '"' + self.__class__.__name__ + self.__bfsRand + '"'


    @staticmethod
    def doBFS(action, start):
        workingSet = set([start])
        visited = set()

        while len(workingSet) != 0:
            newWorkingSet = set()
            for node in workingSet:
                newWorkingSet = newWorkingSet.union(node.bfs(action))
            visited = visited.union(workingSet)
            workingSet = newWorkingSet
            workingSet = workingSet.difference(visited)
