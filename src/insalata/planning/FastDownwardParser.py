from insalata.planning.PlanParserBase import PlanParserBase

class FastDownwardParser(PlanParserBase):
    """
    Get an ordered execution plan of functions based on the plan file of Fast-Downward.

    Keyword arguments:
        objects -- A dictionary with all objects associated with the name used for them in the plan.
        functionDict -- A dictionary with all available functions associated with their all lower case name.
        planFile -- Path to the file containing the plan.
    
    Returns:
        A linear ordered list of function pointers from the setup module, associated with their respective parameter. 
    """
    def parsePlan(self, objects, functionDict, planFile):
        lines = [line.rstrip('\n') for line in open(planFile)]               
        lines.pop()
        
        #split each line, function name first, object second
        plan = []
        for l in lines:
            l = l.lstrip('(').rstrip(')')

            f = l.split()[0].lower()    #function name
            
            #all other elements are objects and therefore parameter
            params = tuple([objects[x.lower()] for x in l.split()[1:]])  
            plan.append((functionDict[f],) + params)    #add tuple (function, parameter)
        
        return plan

