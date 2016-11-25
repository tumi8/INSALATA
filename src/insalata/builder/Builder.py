from configobj import ConfigObj
from insalata.builder import *
import os
import importlib
import pkgutil
import sys
import types

BUILD_MODULE = "insalata.builder"

class Builder:
    def __init__(self, builderConfPath, logger):
        """
        Search for a function that solves the given action for an object that specifies 
        a certain hypervisor, template or service.

        :param builderConfPath: Path to the builder config for this Environment.
        :type builderConfPath: str
        """
        self.logger = logger

        self.builderConf = None
        if not os.path.isfile(builderConfPath):
            self.logger.warning("No builder.conf found.")
        else:
            self.builderConf = ConfigObj(builderConfPath)
        self.functions = self.loadFunctions(BUILD_MODULE)

    def loadFunctions(self, packageName):
        """ 
        Import all functions of all functions of a module, recursively, including subpackages

        :param packageName: Name of the package to load functions of.
        :type packageName: str

        :returns: A dictionary with all functions under the given main module.
        :rtype: dict[str, types.Function]
        """
        package = importlib.import_module(packageName)

        results = {}
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__):
            fullName = package.__name__ + '.' + name
            module = importlib.import_module(fullName)

            #get all functions of module 
            functionNames = [f for f in dir(module) if not f.startswith('_')]
            for fn in functionNames:
                f = getattr(module, fn)
                if isinstance(f, types.FunctionType):
                    results[fullName + '.' + fn] = getattr(module, fn) 

            #load submodules if any
            if is_pkg:
                results.update(self.loadFunctions(fullName))
        return results


    def findFunction(self, objId, forAction, forHypervisor=None, forTemplate=None, forService=None):
        """
        Search for a function that solves the given action for an object that specifies 
        a certain hypervisor, template or service.

        :param objId: The global ID of the affected object.
        :type objId: str

        :param forAction: The name of the action to find a function for.
        :type forAction: str

        :param forHypervisor: The name of the action to find a function for.
        :type forHypervisor: str

        :param forTemplate: A list of template properties to find a function for.
        :type forTemplate: str

        :param forService: The name of the service to find a function for.
        :type forService: str

        :returns: A reference to a function that can be called based on the given parameters.
        :rtype: function
        """
        #look at the builder.conf in order to find a possible exception given for this object and action specifically
        if objId in self.builderConf:
            if forAction in self.builderConf[objId]:
                function = self.builderConf[objId][forAction]
                return self.functions[BUILD_MODULE + "." + function]

        #else
        #find a suitable method by looking at the forHypervisor/forTemplate/forServicesplitted 
        
        #get all functions for the specified action (list comprehension for readability)
        functionForAction = [f for _, f in self.functions.items() if hasattr(f, 'action') and f.action == forAction]
        
        #the decorator adds all attributes, possibly with None
        suitableActions = [f for f in functionForAction 
            if (not f.hypervisor or f.hypervisor == forHypervisor) 
            and (not f.template or (forTemplate and len(set(forTemplate).intersection(set(f.template))) > 0)) 
            and (not f.service or f.service == forService)
        ]

        #order by not-None attributes in order to find the most suitable match
        suitableActions = sorted(suitableActions, reverse=True, key=lambda f: 
            (1 if f.hypervisor else 0) 
            + (len(set(forTemplate).intersection(set(f.template))) if f.template else 0)
            + (1 if f.service else 0)
        )

        if len(suitableActions) > 0: 
            return suitableActions[0]
        else: 
            self.logger.error("No builder found for object '{0}' and action '{1}'.".format(objId, forAction))


###################################################################################################
#  Functions for all steps defined in the planners domain which will then call the right builder  #
###################################################################################################

    def createNetwork(self, config, network):
        f = self.findFunction(network.getGlobalID(), "createNetwork", network.getLocation().getType())
        f(self.logger, network)

    def createHost(self, config, host):
        f = self.findFunction(host.getGlobalID(), "createHost", host.getLocation().getType(), host.getTemplate().getMetadata())
        f(self.logger, host)

    def createInterface(self, config, interface):
        f = self.findFunction(interface.getGlobalID(), "createInterface", interface.getHost().getLocation().getType(), interface.getHost().getTemplate().getMetadata())
        f(self.logger, interface)

    def boot(self, config, host):
        f = self.findFunction(host.getGlobalID(), "boot", host.getLocation().getType(), host.getTemplate().getMetadata())
        f(self.logger, host)

    def bootAndNamed(self, config, host):
        host.setNameApplied(True)
        self.boot(config, host)

    def reboot(self, config, host):
        f = self.findFunction(host.getGlobalID(), "reboot", host.getLocation().getType(), host.getTemplate().getMetadata())
        f(self.logger, host)

    def rebootAndNamed(self, config, host):
        host.setNameApplied(True)
        self.reboot(config, host)

    def bootUnnamed(self, config, host):
        host.setNameApplied(False)
        self.boot(config, host)

    def shutdown(self, config, host):
        f = self.findFunction(host.getGlobalID(), "shutdown", host.getLocation().getType(), host.getTemplate().getMetadata())
        f(self.logger, host)

    def name(self, config, host):
        f = self.findFunction(host.getGlobalID(), "name", host.getLocation().getType(), host.getTemplate().getMetadata())
        f(self.logger, host)

    def configureService(self, config, service):
        serviceTypeOrProduct = service.getProduct() if service.getProduct() else service.getType()
        f = self.findFunction(service.getGlobalID(), "configureService", forTemplate=service.getHost().getTemplate().getMetadata(), forService=serviceTypeOrProduct)
        f(self.logger, service, config)

    def configureDns(self, config, service):
        serviceTypeOrProduct = service.getProduct() if service.getProduct() else service.getType()
        f = self.findFunction(service.getGlobalID(), "configureDns", forTemplate=service.getHost().getTemplate().getMetadata(), forService=serviceTypeOrProduct)
        f(self.logger, service, config)

    def configureDhcp(self, config, service):
        serviceTypeOrProduct = service.getProduct() if service.getProduct() else service.getType()
        f = self.findFunction(service.getGlobalID(), "configureDhcp", forTemplate=service.getHost().getTemplate().getMetadata(), forService=serviceTypeOrProduct)
        f(self.logger, service, config)

    def configureRouting(self, config, host):
        f = self.findFunction(host.getGlobalID(), "configureRouting", forTemplate=host.getTemplate().getMetadata())
        f(self.logger, host)

    def configureFirewall(self, config, host):
        f = self.findFunction(host.getGlobalID(), "configureFirewall", forTemplate=host.getTemplate().getMetadata())
        f(self.logger, host)

    def configureCpus(self, config, host):
        f = self.findFunction(host.getGlobalID(), "configureCpus", host.getLocation().getType(), host.getTemplate().getMetadata())
        f(self.logger, host)

    def configureMemory(self, config, host):
        f = self.findFunction(host.getGlobalID(), "configureMemory", host.getLocation().getType(), host.getTemplate().getMetadata())
        f(self.logger, host)

    def configureInterface(self, config, interface):
        f = self.findFunction(interface.getGlobalID(), "configureInterface", interface.getHost().getLocation().getType(), interface.getHost().getTemplate().getMetadata())
        f(self.logger, interface)

    def unconfigureInterface(self, config, interface):
        f = self.findFunction(interface.getGlobalID(), "unconfigureInterface", interface.getHost().getLocation().getType(), interface.getHost().getTemplate().getMetadata())
        f(self.logger, interface)

    def configureNetwork(self, config, interface):
        f = self.findFunction(interface.getGlobalID(), "configureNetwork", interface.getHost().getLocation().getType(), interface.getHost().getTemplate().getMetadata())
        f(self.logger, interface)
        
    def configureMtu(self, config, interface):
        f = self.findFunction(interface.getGlobalID(), "configureMtu", interface.getHost().getLocation().getType(), interface.getHost().getTemplate().getMetadata())
        f(self.logger, interface)

    def configureRate(self, config, interface):
        f = self.findFunction(interface.getGlobalID(), "configureRate", interface.getHost().getLocation().getType(), interface.getHost().getTemplate().getMetadata())
        f(self.logger, interface)

    def addConfigNameNetwork(self, config, network):
        f = self.findFunction(network.getGlobalID(), "addConfigNameNetwork", network.getLocation().getType())
        f(self.logger, network, config.getID())

    def addConfigNameHost(self, config, host):
        f = self.findFunction(host.getGlobalID(), "addConfigNameHost", host.getLocation().getType())
        f(self.logger, host, config.getID())

    def addConfigNameDisk(self, config, disk):
        f = self.findFunction(disk.getGlobalID(), "addConfigNameDisk", disk.getHost().getLocation().getType())
        f(self.logger, disk, config.getID())

    def addDisk(self, config, disk, host):
        f = self.findFunction(disk.getGlobalID(), "addDisk", host.getLocation().getType())
        f(self.logger, disk, host)

    def removeDisk(self, config, disk):
        f1 = self.findFunction(disk.getGlobalID(), "removeConfigNameDisk", disk.getHost().getLocation().getType())
        remaining = f1(self.logger, disk, config.getID())
        #destroy if there are no remaining configs referencing this disk
        if remaining == []:
            f2 = self.findFunction(disk.getGlobalID(), "removeDisk", disk.getHost().getLocation().getType(), disk.getHost.getTemplate().getMetadata())
            f2(self.logger, disk)

    def removeNetwork(self, config, network):
        f1 = self.findFunction(network.getGlobalID(), "removeConfigNameNetwork", network.getLocation().getType())
        remaining = f1(self.logger, network, config.getID())
        #destroy if there are no remaining configs referencing this network
        if remaining == []:
            f2 = self.findFunction(disk.getGlobalID(), "removeNetwork", network.getLocation().getType())
            f2(self.logger, network)

    def removeHost(self, config, host):
        f1 = self.findFunction(host.getGlobalID(), "removeConfigNameHost", host.getLocation().getType())
        remaining = f1(self.logger, host, config.getID())
        #destroy if there are no remaining configs referencing this host
        if remaining == []:
            f2 = self.findFunction(host.getGlobalID(), "removeHost", host.getLocation().getType())
            f2(self.logger, host)

    def removeInterface(self, config, interface):
        f = self.findFunction(host.getGlobalID(), "removeInterface", interface.getHost().getLocation().getType())
        f(self.logger, interface)

    def deleteHost(self, config, host):
        pass