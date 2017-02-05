CONF_FILE = "/etc/insalata/insalata.conf"

import sys, socket
import signal
from functools import partial
from configobj  import ConfigObj, ParseError
from insalata.EnvironmentHandler import EnvironmentHandler
from insalata.Logging import createLogger, getLogLevel
from xmlrpc.server import SimpleXMLRPCServer
from inspect import signature, Parameter, getdoc

class Insalata:
    """
    Daemon for the insalata application.
    """

    def __init__(self, stdin='/dev/stdin', stdout='/dev/stdout', stderr='/dev/stderr'):
        """
        Create a new daemon for the insalata application.

        :param stdin: File to use as stdin
        :type stdin: :class:'file' class

        :param stdout: File to use as stdout
        :type stdout: :class:'file' class

        :param stderr: File to use as stderr
        :type stderr: :class:'file' class
        """
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.environments = dict()
        self.config = None
        self.level = None
        self.logSize = None
        self.backupCount = None
        self.logger =  None

    def __handleSigterm__(self, *args, **kwargs):
        self.logger.info("Received SIGTERM, stopping all environments.")

        self.__dispose__(exitCode = 0)

    def __dispose__(self, exitCode=0):
        #stop all environments
        for env in self.environments:
            env.stopEnvironment()
        sys.exit(exitCode)

    def __start__(self):
        """
        Startup the service functionality:
            Read configuration file
            Startup RPC-Server
            Startup EnvironmentHandlers
        """
        #sigterm handler
        signal.signal(signal.SIGTERM, partial(self.__handleSigterm__))
        try:
            self.config = ConfigObj(CONF_FILE)
        except ParseError:
            print("Unable to parse config file: {0}".format(CONF_FILE), file=sys.stderr)
            sys.stderr.flush()
            self.__dispose__(exitCode = 1)
        try:
            self.__createGlobalLogger__(self.config)
            self.__initEnvironments__()

            #init xmlrpc server
            #ip and port in insalata.conf
            server = SimpleXMLRPCServer((self.config["rpcServerAddress"], int(self.config["rpcServerPort"])))
            server.register_instance(self, allow_dotted_names=True)
            self.logger.info("Insalata started")
            server.serve_forever()
        except PermissionError:
            self.logger.critical("Illegal Port. Can access port {0}.".format(self.config["rpcServerPort"]))
            self.__dispose__(exitCode = 1)
        except (OSError, socket.gaierror):
            self.logger.critical("Illegal Port or Address. Can not open endpoint {0}:{1}.".format(self.config["rpcServerAddress"], self.config["rpcServerPort"]))
            self.__dispose__(exitCode = 1)
        except KeyError as ex:
            print("Unable to parse config file: {0}".format(CONF_FILE), file=sys.stderr)
            sys.stderr.flush()
            self.__dispose__(exitCode = 1)
        except Exception as e:
            self.logger.critical("Error while starting/stopping INSALATA.")
            self.__dispose__(exitCode = 1)

    def __createGlobalLogger__(self, config):
        """
        Create the global logger used by the service.

        :param config: Configuration used by the service
        :type config: :class:'configparser.ConfigParser'
        """
        self.level = getLogLevel(config["logLevel"])

        if (self.level is None):
            self.level = getLogLevel("debug")

        self.logSize = int(config["logSize"])
        self.backupCount = int(config["backup"])

        self.logger = createLogger("Global", "insalata.log", self.level, self.logSize, self.backupCount)

    def __initEnvironments__(self):
        """
        Initialize the EnvironmentHandlers and all Collectors.
        """
        if "environments" not in self.config:
            self.logger.warning("No section 'environments' found in config {0}.".format(CONF_FILE))
            return
        for environmentName in self.config["environments"]:
            envConfig = self.config["environments"][environmentName]
            try:
                envPath = envConfig["path"]
                environment = EnvironmentHandler(environmentName, envPath, self.level, self.logSize, self.backupCount, self.logger)

                self.environments[environmentName] = environment
                self.logger.info("Starting new environment: {0}".format(environmentName))
                environment.start()
                self.logger.info("Started environment: {0}!".format(environmentName))
            except KeyError as e:
                self.logger.error("Error in config for environment {0}. Missing key {1}.".format(environmentName, e.args[0]))
                raise
            except:
                raise
                self.logger.critical("Not able to start environment: {0}!".format(environmentName))


    def uploadConfiguration(self, environmentName, fileName, xmlData):
        """
        Upload a new configuration file.

        :param environmentName: Name of the environment the XML will be part of
        :type environmentName: str

        :param fileName: Name of the file.
        :type fileName: str

        :param xmlData: Xml-content as string
        :type xmlData: str
        """
        if environmentName in self.environments:
            self.environments[environmentName].uploadConfiguration(fileName, xmlData)
            return "Successfully uploaded configuration '{0}'.".format(fileName)
        else:
            return "Environment '{0}' unkown.".format(environmentName)

    def listFiles(self, environmentName):
        """
        Get a list of all files associated with an environment.

        :param environmentName: Name of the environment the XML will be part of
        :type environmentName: str

        :returns: The name of all files inside the given environment.
        :rtype: [str]
        """
        if environmentName in self.environments:
            files = self.environments[environmentName].getFiles()
            return "-------------------- Found {0} file(s) --------------------\n{1}".format(len(files), '\n'.join(files))
        else:
            return ["Environment '{0}' unkown.".format(environmentName)]

    def getFile(self, environmentName, fileName):
        """
        Get a list of all files associated with an environment.

        :param environmentName: Name of the environment the XML file is part of
        :type environmentName: str

        :param environmentName: Name of the environment the XML file is part of
        :type environmentName: str

        :returns: The name of all files inside the given environment.
        :rtype: [str]
        """
        if environmentName in self.environments:
            if fileName in self.environments[environmentName].getFiles():
                content = self.environments[environmentName].readFile(fileName)
            return "-------------------- Found file '{0}' --------------------\n{1}".format(fileName, content)
        else:
            return "Environment '{0}' unkown.".format(environmentName)

    def applyConfiguration(self, environmentName, fileName):
        """
        Apply a previously uploaded configuration. 

        :param environmentName: Name of the environment the new configuration will be applied to.
        :type environmentName: str

        :param fileName: Name of the file.
        :type fileName: str
        """
        if environmentName in self.environments:
            return self.environments[environmentName].applyConfig(fileName)
        else:
            return "Environment '{0}' unkown.".format(environmentName)

    def applyEnvironment(self, environmentFrom, environmentTo):
        """
        Apply a previously uploaded configuration. 

        :param environmentFrom: Name of the environment to apply to another location.
        :type environmentFrom: str

        :param environmentTo: Name of the environment on which environmentFrom will be deployed.
        :type environmentTo: str

        :param fileName: Name of the file.
        :type fileName: str
        """
        pass

    def exportEnvironmentToXml(self, environmentName, fileName):
        """
        Triggers the output of the information collected about this environment as an XML.

        :param environmentName: The names of the environment to export.
        :type environmentName: str

        :param fileName: The filename to use for exporting the information to the environment's data directory.
        :type fileName: str
        """
        if environmentName in self.environments:
            process = self.environments[environmentName].printXml(fileName)
            return "Saved exported information as '{0}'".format(fileName)
        else:
            return "Environment '{0}' unkown.".format(environmentName)

    def getEnvironments(self):
        """
        Retrieves a list of all environments.

        :returns: The names of all environments.
        :rtype: [str]
        """
        return '\n'.join([str(x) for x in self.environments.keys()])

    def getSetupProgress(self, environmentName):
        """
        Get the current setup process of an environment.

        :param environmentName: Name of the environment to get the setup process of.
        :type environmentName: str
        """
        if environmentName in self.environments:
            process = self.environments[environmentName].getSetupProgress()
            return "Process of '{0}': {1}".format(environmentName, process)
        else:
            return "Environment '{0}' unkown.".format(environmentName)

    def getCommands(self):
        """
        Retrieve a list of all commands publicly available for clients of this service.

        :returns: A dictionary with all publicly available commands, their minimum, maximum number of parameter associated and their docstring for description.
        :rtype: {str: (int, int, string) }
        """
        functionNames = [f for f in dir(Insalata) if not f.startswith('_')]

        #create a dictionary of all functions associated with a tuple containing their minimal and maximal amount of paramters (sorry for the rather unreadable code)
        functionDict = {
            fn : (
                len(
                    [p.name for p in signature(getattr(Insalata, fn)).parameters.values() if not p.name == "self" and p.default == Parameter.empty]
                ), 
                len(
                    [p.name for p in signature(getattr(Insalata, fn)).parameters.values() if not p.name == "self"]
                ),
                str(getdoc(getattr(Insalata, fn)))
            )
            for fn in functionNames
        }
        return functionDict
