import os
import queue
import configobj
import datetime
import traceback
import threading
import importlib
import time
from configobj  import ConfigObj, ConfigObjError
from queue import PriorityQueue
from functools import partial
#from threading import Thread
from lxml import etree

from insalata.Timer import Timer
from insalata.model.Graph import Graph
from insalata.builder.Builder import Builder
from insalata.Logging import createLogger
from insalata.scanner.Worker import Worker
from insalata.scanner.modules import XmlScanner
from insalata.helper import diff
from insalata.planning import planner
import insalata.XmlPrint

JOBS = 20
PRIORITY = 5
HIGHEST_PRIO = 1
TIMEOUT = 30
DEFAULT_QUEUE_SIZE = 20
CONFIG_FILE = "environment.conf"

class EnvironmentHandler(threading.Thread):
    """
    The EnvironmentHandler class controls the collecting of information in one environment.
    Each handler executes independent and concurrent to the other ones controled by the 
    service.
    """

    def __init__(self, name, environmentPath, logLevel, logSize, backupCount, globalLogger):
        """
        Creates a new EnvironmentHandler object.
        If logLevel, logSize or backupCount is given in the EnvironmentHandler config
        this one will be prefered.

        :param name: Name of this environment
        :type name: str

        :param environmentPath: Path to the directory of this environment
        :type environmentPath: str

        :param logLevel: Global logLevel of the system: Integer dpecifiying the logLevel(Used by python logging)
        :type: int

        :param logSize: Global size for a log-file
        :type logSize: int

        :param backupCount: Globaly set number of log backups to store
        :type: int
        """
        threading.Thread.__init__(self)
        self.name = name
        self.config = None
        self.logger = None
        self.path = environmentPath
        self.globalLogger = globalLogger

        self.collectorModules = dict()
        self.timers = dict()
        self.workingSet = list()

        self.graph = Graph(self.name)
        self.workers = list()
        self.__stopEvent = threading.Event()

        self.continuousExporters = dict()
        self.triggeredExporters = dict()
        self.exportTrigger = dict()

        self.taskState = ""

        try:
            self.loadConfig()
            self.dataPath = self.config["dataDirectory"]
            self.dataPath = self.dataPath if os.path.isabs(self.dataPath) else os.path.join(self.path, self.dataPath) #Get the absolute path of the data directory
            self.initLogger(self.config["logLevel"] if "logLevel" in self.config else logLevel, 
                self.config["logSize"] if "logSize" in self.config else logSize,
                self.config["backupCount"] if "backupCount" in self.config else backupCount)

            self.queue = PriorityQueue(self.config["queueSize"] if "queueSize" in self.config else DEFAULT_QUEUE_SIZE)

            self.logger.info("Environment started!")
        except KeyError as e:
            if self.logger is not None:
                self.logger.critical("Missing parameter: {0}".format(e.args[0]))
            else:
                self.globalLogger.critical("Missing parameter for environment {0}: {1}".format(self.name, e.args[0]))
            self.__stopEvent.set()
        except Exception as e:
            self.__stopEvent.set()
            raise

    def getSetupProgress(self):
        return self.taskState

    def getName(self):
        return self.name

    def loadConfig(self):
        """
        Load the configuration for this EnvironmentHandler.
        """
        configPath = os.path.join(self.path, CONFIG_FILE)
        if not os.path.isfile(configPath):
            self.globalLogger.critical("Config file for environment {0} does not exist!".format(self.getName()))
            self.__stopEvent.set()
        self.config = ConfigObj(configPath)
        if self.config == {}:
            self.globalLogger.critical("Config file for environment {0} is empty!".format(self.getName()))
            self.__stopEvent.set()

    def run(self):
        """
        This method is executed when the thread of this handler is started.
        It triggers the collector modules in their specified time intervals.
        """
        try:
            if self.__stopEvent.isSet():
                self.logger.critical("Environment is not set on running state!")
                return
            if self.initScanner() is None:
                self.logger.error("Error while initializing scanner.")
                return
            self.initExporters()
            self.logger.info("Environment running...")
            while not self.__stopEvent.isSet():
                try:
                    _, interval, name = self.queue.get(True, TIMEOUT) #Priority is only used by queue
                    self.logger.debug("Starting collector module {}.".format(name))
                    if "config" not in self.config["modules"][name]:
                        self.logger.error("No configuration given for collector {0}.".format(name))
                    else:
                        configPath = self.config["modules"][name]["config"]
                        configPath = configPath if os.path.isabs(configPath) else os.path.join(self.path, configPath)
                        connectionInfo = ConfigObj(configPath)
                        if connectionInfo == {}:
                            self.logger.warning("Connection information for module {0} empty.".format(name))
                        connectionInfo["name"] = name

                        #interval -1 means "No restart" 
                        if interval != -1:
                            self.timers[name] = Timer(int(interval), self.executeScan, [name])

                        worker = Worker(partial(self.collectorModules[name], self.graph, connectionInfo ,self.logger), name, partial(self.finishedCallback, name, interval), self.logger)
                        self.workers.append(worker)
                        worker.start()
                except ConfigObjError:
                    self.logger.error("Can not parse connectionInfo for module {0}: Path: {1}.".format(name, configPath))
                except queue.Empty:
                    #Just do nothing. This is a normal case
                    self.logger.debug("No job to handle.")
                except KeyError as e:
                    self.logger.error("Missing key '{0}' in configuration file for module {1}.".format(e.args[0], name))
                except Exception as e:
                    self.logger.debug("{0}: {1}".format(type(e), traceback.format_exc()))
                    self.logger.error("Error while executing scan!")
        except Exception as e:
            self.logger.critical("Error in EnvironmentHandler: {}".format(str(e)))

    def finishedCallback(self, module, interval, worker):
        """
        All Worker threads will call this method if their work is finished.

        If the interval is -1 (no_restart) this method only removes the worker from the list of workers
        If the interval != -1 the new timer for this collector module will be started (created by run method)

        :param module: Collector module finished its work
        :type module: str

        :param interval: Timer interval the module uses
        :type interval: int

        :param worker: Worker thread which executed the collector module
        :type worker: insalata.scanner.Worker.Worker
        """
        if interval >= 0:
            self.timers[module].start() # Start the timer if requested and the timer shall restart (no -1)
        self.workers.remove(worker)

    def initExporters(self):
        # Continuous
        if "continuousExporters" in self.config.keys():
            for exporter in (self.config["continuousExporters"] if isinstance(self.config["continuousExporters"], list) else [self.config["continuousExporters"]]):
                try:
                    module = importlib.import_module("insalata.export.continuous.{0}".format(exporter))
                    self.logger.debug(str(module))
                    self.continuousExporters[exporter] = getattr(module, "Exporter")(self.graph.getObjectNewEvent(), self.graph.getObjectDeletedEvent(),
                                                                                        self.graph.getObjectChangedEvent(), self.logger, self.dataPath)
                    self.logger.debug("Added continuous exporter {0}.".format(exporter))
                except ImportError:
                    self.logger.error("No exporter {0}.py in insalata.export.continuous!".format(exporter))
                    continue
                except AttributeError as e:
                    self.logger.debug(str(e))
                    self.logger.error("No class 'Exporter' in module {0}!".format(exporter))
                    continue

        # Triggered
        if "triggeredExporters" in self.config.keys():
            for exporter in list(self.config["triggeredExporters"].keys()):
                try:
                    module = importlib.import_module("insalata.export.triggered.{0}".format(exporter))
                    self.triggeredExporters[exporter] = getattr(module, "export")

                    if("interval" in self.config["triggeredExporters"][exporter] and self.config["triggeredExporters"][exporter] != -1):
                        interval = self.config["triggeredExporters"][exporter]
                        if(interval < 1):
                            self.exportTrigger[exporter] = Timer(interval, partial(self.startTriggeredExporter, exporter, interval))
                            self.logger.debug("Started continuous exporter '{0}'.".format(exporter))
                        else:
                            self.logger.error("Invalid interval configured for exporter '{0}'!".format(exporter))
                    else:
                        self.logger.error("No interval configured for triggered exporter '{0}'".format(exporter))
                except ImportError:
                    self.logger.error("No exporter {0}.py in insalata.export.continuous!".format(exporter))
                    continue
                except AttributeError:
                    self.logger.error("No 'export' method in module {0}!".format(exporter))
                    continue

    def startTriggeredExporter(self, exporter, interval, configuration=None):
        graph = self.graph
        if configuration:
            graph = Graph.copy(configuration)
        self.triggeredExporters[exporter](self.dataPath, graph)
        self.exportTrigger[exporter] = Timer(interval, partial(self.startTriggeredExporter, exporter, interval))


    def initScanner(self):
        """
        Initialize the scanner of this environment.
        Initialze working set with values from config and load configuration 
        of scanning modules.
        """
        self.workingSet = self.config["workingSet"] if "workingSet" in self.config else None
        if self.workingSet is None:
            self.config["workingSet"] = []
            self.config.write()

        #Load collector modules
        if "modules" not in self.config:
            self.logger.warning("No collector modules defined for environment.")
            return
        for collectorName in self.config["modules"].keys():
            config = self.config["modules"][collectorName]
            if config.__class__ != configobj.Section:
                continue

            #Load the "scan" function of the module
            if "type" not in config:
                self.logger.error("No type field found in config for collector module {0}.".format(collectorName))
                continue
            collectorType = config["type"]

            try:
                module = importlib.import_module("insalata.scanner.modules.{0}".format(collectorType))
                self.collectorModules[collectorName] = getattr(module, "scan")
            except ImportError:
                self.logger.error("No module {0}.py!".format(collectorType))
                continue
            except AttributeError:
                self.logger.error("No collector in module {0}! Method 'scan' missing!".format(collectorType))
                continue

        return self.initScanningSchedule()

    def initLogger(self, logLevel, logSize, backupCount):
        """
        Method initializes the logger for this environment.
        For systemwide unique naming: logger_<thread_id> is taken as logger-name.
        This naming is useful to get the logger in other modules.

        :param logLevel: The defined logLevel for this scanner
        :type logLevel: int ( by python logging class)

        :param logSize: Size one single log file 
        :type logSize: int

        :param backupCount: Number of log-Files to backup
        :type backupCount: int
        """
        logname = "logger_{0}".format(threading.current_thread().ident)
        self.logger = createLogger(logname, "{0}.log".format(self.name), logLevel, logSize, backupCount)


    def initScanningSchedule(self):
        """
        This method initializes the scanning schedule.
        The scanning interval for each scanner will be loaded and a timer for each scanning-module
        will be launched.
        """

        for collectorName in self.collectorModules.keys():
            config = self.config["modules"][collectorName]
            if config.__class__ != configobj.Section:
                continue

            interval = int(config["interval"] if "interval" in config else -1)
            if interval == -1:
                self.logger.warning("No intervall/ interval -1 defined for collector module {0}. This module will be started only once!".format(collectorName))
                self.queue.put((PRIORITY, interval, collectorName), True, TIMEOUT)
                self.timers[collectorName] = None
            else:
                self.timers[collectorName] = Timer(int(interval), self.executeScan, [collectorName])
        for timer in self.timers.keys():
            self.timers[timer].start()
        return True

    def executeScan(self, collectorName):
        """
        This method adds the scanners to the execution queue.

        :param collectorName: Name of the scanner to launch
        :type collectorName: str
        """
        try:
            self.logger.debug("Adding scanner to execution-queue: {0}".format(collectorName))

            interval = int(self.config["modules"][collectorName]["interval"])

            self.queue.put((PRIORITY, interval, collectorName), True, TIMEOUT)
        except queue.Full:
            self.logger.error("Queue is full. Not able to add scanner {0}.".format(collectorName))
        except KeyError as e:
            self.logger.error("Missing interval for module {0}. Key: {1}".format(collectorName, e.args[0]))


    def uploadConfiguration(self, fileName, data):
        """
        This method uploads a configuration file and stores it into the environment's data directory.

        :param fileName: Name of the file.
        :type fileName: str

        :param data: Xml-content as string
        :type data: str
        """
        filePath = os.path.join(self.dataPath, fileName)

        with open(filePath, 'w+') as xml:
            xml.write(data)

    def getFiles(self):
        """
        List all files in the data directory
        
        :returns: A list of all files in this environment's data directory
        :rtype: [str]
        """
        return os.listdir(self.dataPath)

    def readFile(self, fileName):
        """
        Read the content of a file of this environment.
        
        :param fileName: Name of the file.
        :type fileName: str

        :returns: The content of the file that has been read.
        :rtype: str
        """
        with open(os.path.join(self.dataPath, fileName), 'r') as f:
            return f.read()

# Done by export -> Not used in environment
    def updateConfigs(self, path):
        pass
#        """
#        Update the configuration files.
#        Method loads all handeled configurations and prints the collected information
#        devided into different files for each configuration.

#        :param path: Path to the data directory where the configuration shall be stored
#        :type path: str
#        """
#        configs = set()
#        scanned = self.scanner.getConfig()
#        for name in self.workingSet:
#            hosts = [x for x in scanned['hosts'] if name in x.getConfigNames()]
#            networks = [x for x in scanned['networks'] if name in x.getConfigNames()]
#            server = scanned['servers']
#            vlans = scanned['vlans']
#            firewalls = scanned['firewalls']
#            services = scanned['services']
#            
#            hostNames = set()
#            for host in hosts:#Get all hostnames in config
#                hostNames.add(host.getID())

#            routes = [x for x in scanned['router'] if x.getID() in hostNames]

#            configs.add(Graph(name, networks, hosts, routes, vlans, server, services, firewalls))

#        for configuration in configs:
#            XmlPrint.printXML("{0}/{1}.xml".format(self.dataPath, configuration.getID()), configuration)

    def doFullScan(self):
        """
        Execute a full scan in this environment.
        This means that every configured collector module will be launched one time.
        """
        self.logger.info("Next job is a full scan.")
        for timer in self.timers.keys():
            self.timers[timer].cancel()
        try:
            for module in self.collectorModules.keys():
                self.queue.put((HIGHEST_PRIO, -1, module), True, TIMEOUT)
        except queue.Full:
            self.logger.error("Job queue is full. Not able to enqueue full scan.")

    def applyConfig(self, newConfigFileName):
        """
        Apply a given configuration to the environment.
        This method processes the new configuration, freezes this environment and copies the relevant part.
        Afterwards a new thread will be launched whichruns planning and setup itself.

        :param newConfigFileName: Name of the previously uploaded configuration containing the configuration to setup
        :type newConfigFileName: str
        """
        try:
            if not (self.taskState.startswith("Finished") or self.taskState == "") :
                return "Another task is already running!!"
            
            startTime = datetime.datetime.now()
            self.logger.info("Starting setup at {0}".format(startTime.strftime("%d.%b.%Y %H.%M.%S")))
            self.logger.info("Freezing Environment '{0}'".format(self.getName()))
            self.freezeEnvironment()

            newConfigPath = os.path.join(self.dataPath, newConfigFileName)
            id = etree.parse(newConfigPath).getroot().attrib["name"]
            self.logger.info("Apply Configuration with ID '{0}'".format(id))

            #generate graph for goal configuration
            newGraph = Graph(id)
            XmlScanner.scan(newGraph, {"name" : "applyLogger", "file" : newConfigPath}, self.logger, None)

            #get current graph
            currentGraph = self.graph.copy(id)
            
            diff.resolveGraph(newGraph)
            diff.resolveGraph(currentGraph)
            diffDict = diff.diff(newGraph, currentGraph)

            self.taskState = "Setup is initializing..."
            self.logger.info(self.taskState)
            t = threading.Thread(target = self.runSetup, args=(newGraph, currentGraph, diffDict, startTime))
            t.start()

            return "The deployment started. Get progress with 'getSetupProgress {0}'".format(self.getName())
        except Exception as e:
            return "{0}: {1}".format(type(e), traceback.format_exc())

    def runSetup(self, newGraph, currentGraph, diffDict, startTime):
        """
        Run the planner and setup the new configuration.
        Afterwards the environment will be unfreezed.

        :param newGraph: Graph to deploy on the environment
        :type newGraph: insalata.model.Graph.Graph

        :param currentGraphy: Graph currently deployed on the environment under the given name
        :type currentGraphy: insalata.model.Graph.Graph

        :param diffDict: Represents the differences between current and new configuration
        :type diffDict: dict

        :param startTime: Time this setup was started
        :type startTime: datetime.datetime
        """

        plan = planner.getPlan(self.logger, currentGraph, newGraph, diffDict)

        self.taskState = "Plan received."
        self.logger.info(self.taskState)

        builder = Builder(os.path.join(self.path, "builder.conf"), self.logger)

        self.taskState = "Start building..."
        self.logger.info(self.taskState)

        initTime = time.gmtime()

        #---------------------------- Measure time -----------------------------
        #with open("/etc/insalata/tmp/timer.txt", 'w') as timerfile:
        #-----------------------------------------------------------------------

        #execute every command of the ordered plan
        for i, cmd in enumerate(plan, start = 1):
            #cmd: (function pointer, function parameter)
            self.taskState = "Call step {0}/{1}: '{2}' on object '{3}'".format(str(i), len(plan), cmd[0].__name__, cmd[1].getID())
            self.logger.info(self.taskState)

            #write timer
            #startTime = time.time()
            #timerfile.write("Starting step {0} at {1}".format(str(i+1), startTime))

            try:
                cmd[0](builder, newGraph, *(cmd[1:]))
            except Exception as e:
                self.logger.error("{0}: {1}".format(type(e), traceback.format_exc()))
                self.logger.error("Error while executing step '{0}'".format(cmd[0].__name__))

        try:
            self.taskState = "Finished setup started at '{0}'.".format(time.strftime("%d.%b.%Y %H:%M:%S", initTime))
            self.logger.info(self.taskState)
            self.unfreezeEnvironment()
        except Exception as e:
                self.logger.error("{0}: {1}".format(type(e), traceback.format_exc()))

    def freezeEnvironment(self):
        """
        Freeze the environment by pausing all module timers and stopping the running collectors.
        """
        self.graph.freeze()
        for module in self.collectorModules:
            self.timers[module].pause()

        for worker in self.workers:
            worker.stop()

        for worker in self.workers:
            worker.join()

    def unfreezeEnvironment(self):
        """
        Unfreeze the envornment by restarting all timers.
        """
        self.logger.info("Unfreezing Environment: {}".format(self.name))
        self.graph.melt()
        for module in self.collectorModules:
            self.timers[module].resume()

    def stopEnvironment(self):
        """
        Stop the environment by stopping all collectors and the Thread of the environment itself.
        """
        for module in self.collectorModules:
            self.timers[module].cancel()

        for worker in self.workers:
            worker.stop()

        for exporter in self.continuousExporters:
            exporter.stop()

        for exporter in self.exportTrigger:
            exporter.cancel()

        self.__stopEvent.set()
        for worker in self.workers:
            worker.join()

    def printXml(self, fileName):
        """
        Prints all the information collected by this environment to XML.

        :param fileName: The filename to use for exporting the information to the environment's data directory.
        :type fileName: str
        """
        filePath = os.path.join(self.dataPath, fileName)
        insalata.XmlPrint.printXML(filePath, self.graph)
