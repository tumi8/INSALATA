from abc import ABCMeta, abstractmethod

class PlanParserBase(metaclass=ABCMeta):

    @abstractmethod
    def parsePlan(self, objects, functionDict, planFile):
        pass
