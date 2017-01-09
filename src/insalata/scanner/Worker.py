import threading
import sys
import traceback

class Worker(threading.Thread):
    def __init__(self, target, collectorModuleName, finishedCallback, logger):
        threading.Thread.__init__(self)

        self.__stopEvent = threading.Event()
        self.target = target
        self.finishedCallback = finishedCallback
        self.logger = logger
        self.CMName = collectorModuleName
        self.setDaemon(True)

    def run(self):
        try:
            self.target(self)
        except KeyError as e:
            self.logger.error("Missing key '{0}' in configuration file for module {1}.".format(e.args[0], self.CMName))
        except Exception as e:
            self.logger.error("Error while executing scan!")
            self.logger.error("{0}: {1}".format(type(e), traceback.format_exc().replace("\n", "--")))

        if not self.__stopEvent.isSet():
            self.finishedCallback(self)

    def stop(self):
        self.__stopEvent.set()

    def stopRequested(self):
        return self.__stopEvent.isSet()
