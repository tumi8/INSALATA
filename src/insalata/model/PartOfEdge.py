from insalata.model.Edge import Edge

class PartOfEdge(Edge):
    def __init__(self, start, end, collectorName=None, timeout=None, association=None, changed=None):
        """
        Create a new part of relationships between two nodes.
        Sematics: "start is part of end"

        """
        Edge.__init__(self, start, end, collectorName=collectorName, timeout=timeout, association=association, changed=changed)