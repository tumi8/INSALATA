from functools import partial
import datetime
from insalata.Timer import Timer
import json
import threading
import os

WRITE_INTERVAL = 1
OUTFILE = "/etc/insalata/testEnv/data/changeLog.txt"
TYPE="w"

class Exporter:
    def __init__(self, onNewEvent, onDeletedEvent, onChangedEvent, logger, outputDirectory):
        onNewEvent.add(partial(self.onNewHandler))
        onChangedEvent.add(partial(self.onChangedHandler))
        onDeletedEvent.add(partial(self.onDeletedHandler))

        self.buffer = list()
        self.outFile = os.path.join(outputDirectory, "jsonChangeLog.txt")
        self.logger = logger

        self.writer = Timer(WRITE_INTERVAL, partial(self.writeFile))
        self.writer.start()
        self.__stopEvent = threading.Event()

    def stop(self):
        self.writer.cancel()
        self.__stopEvent.set()

    def onNewHandler(self, sender, args):
        self.logger.debug("Received onNewEvent writing to file: {0}".format(self.outFile))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d@%H:%M:%S")
        message = {"time" : timestamp,
                "type" : "new",
                "objectType" : args["objectType"],
                "initialValues" : args["values"]}
        self.buffer.append(json.dumps(message))

    def onChangedHandler(self, sender, args):
        self.logger.debug("Received onChangedEvent writing to file: {0}".format(self.outFile))
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d@%H:%M:%S")
            message = {"time" : timestamp,
                    "type" : "change_" + args["type"],
                    "objectType" : args["objectType"],
                    "object" : args["object"],
                    "value" : args["value"]}
            if "member" in args:
                message["member"] = args["member"]
            self.buffer.append(json.dumps(message))
        except KeyError as e:
            print(str(args))

    def onDeletedHandler(self, sender, args):
        self.logger.debug("Received onDeletedEvent writing to file: {0}".format(self.outFile))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d@%H:%M:%S")
        message = {"time" : timestamp,
                "type" : "delete",
                "objectType" : args["objectType"],
                "object" : args["object"]}
        self.buffer.append(json.dumps(message))

    def writeFile(self):
        if len(self.buffer) > 0:
            try:
                with open(self.outFile, TYPE) as fileHandler:
                    for entry in self.buffer:
                        print(entry, file=fileHandler)
            except:
                self.logger.error("Cannot print JSON change log to file {0}.".format(self.outFile))
        if not self.__stopEvent.isSet():
            self.writer = Timer(WRITE_INTERVAL, partial(self.writeFile))
            self.writer.start()
