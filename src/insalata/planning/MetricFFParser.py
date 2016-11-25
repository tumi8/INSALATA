from insalata.planning.PlanParserBase import PlanParserBase

class MetricFFParser(PlanParserBase):
    """
    Get an ordered execution plan of functions based on the plan file of Metric-FF.

    Keyword arguments:
        objects -- A dictionary with all objects associated with the name used for them in the plan.
        functionDict -- A dictionary with all available functions associated with their all lower case name.
        planFile -- Path to the file containing the plan.
    
    Returns:
        A linear ordered list of function pointers from the setup module, associated with their respective parameter. 
    """
    def parsePlan(self, objects, functionDict, planFile):
        lines = [line.rstrip('\n') for line in open(planFile)]                  
        
        #split each line, function name first, object second
        plan = []
        for l in lines:
            #add tuple (function, parameter)
            plan.append((functionDict[l.split()[0].lower()], objects[l.split()[1].lower()]))    

        #ONLY WORKS FOR A SINGLE PARAMETER