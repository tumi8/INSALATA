from xml.etree.ElementTree import SubElement
from insalata.model.Node import Node
from configobj import ConfigObj
import os
from insalata.model.PartOfEdge import PartOfEdge

LOCATIONS_CONF = "/etc/insalata/locations.conf"


class Location(Node):
    def __init__(self, id, collectorName=None, timeout=None):
        Node.__init__(self, collectorName=collectorName, timeout=timeout)

        self.__id = id.lower()
        self.__type = None
        self.__defaultTemplate = None

        #get the type of the Location
        if os.path.isfile(LOCATIONS_CONF):
            locationConf = ConfigObj(LOCATIONS_CONF)
            if self.__id in locationConf:
                loc = locationConf[self.__id]
                if 'hypervisor' in loc:
                    self.__type = loc['hypervisor']                   
                #read all templates
                if 'templates' in loc:
                    for k in loc['templates'].keys():
                        metadata = ""
                        if 'metadata' in loc['templates'][k]: 
                            metadata = loc['templates'][k]['metadata'] 
                        self.addTemplate(Template(k, metadata))
                #get the default template
                if "default_template" in loc:
                    self.__defaultTemplate = [t for t in self.getTemplates() if t.getID() == loc['default_template']]
                    if len(self.__defaultTemplate) > 0:
                        self.__defaultTemplate = self.__defaultTemplate[0]

    def getDefaultTemplate(self):
        """
        The default template of this Location (defined in the settings)
        :param getDefaultTemplate: The default template of this location
        """
        return self.__defaultTemplate

    def delete(self):
        """
        Delete this node.
        This method overrides 'delete' from the Node classas we want to delete all templates when deleting the Location.
        """
        templates = self.getTemplates()
        for template in templates:
            template.delete()
        super().delete()

    def addTemplate(self, template):
        """
        Add a template to this location.

        :param template: Template to add
        :type template: insalata.model.Template.Template
        """
        edges = [e for e in self.getEdges() if e.getOther(self) == template]
        if len(edges) == 0:
            PartOfEdge(template, self)

    def getTemplates(self):
        return self.getAllNeighbors(Template)

    def getID(self):
        return self.__id

    def getGlobalID(self):
        return self.getID()

    def getType(self):
        return self.__type

    #Print information to XML Format
    def toXML(self, root):
        locationEl = SubElement(root, "location")
        locationEl.attrib["id"] = self.getID()

from insalata.model.Template import Template