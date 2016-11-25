from insalata.model.Node import Node

class Template(Node):
    def __init__(self, id, metadata):
        Node.__init__(self)

        self.id = id
        self.metadata = metadata

    def getID(self):
        return self.id

    def getGlobalID(self):
        loc = self.getLocation()
        if loc:
            return loc.getID() + "_" + self.getID()
        return self.getID()

    def getLocation(self):
        loc = self.getAllNeighbors(Location)
        return list(loc)[0] if len(loc) > 0 else None

    def getMetadata(self):
        return self.metadata

from insalata.model.Location import Location
