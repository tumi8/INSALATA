from insalata.model.PartOfEdge import PartOfEdge

def resolveGraph(config):
    """
    Resolves all "part of" edges in the graph based data structure inside the config and creates sets for the hierarchically structured diff  
    
    Keyword arguments:
        config -- The config to resolve edges of for all subelements
    """
    for x in config.getHosts():
        resolveEdges(x)

def resolveEdges(obj):
    """
    Resolves all "part of" edges in the graph based data structure and creates sets for the hierarchically structured diff  
    
    Keyword arguments:
        obj -- The object to resolve edges of
    """

    #create new properties on the config object based on the adjacent type of all part-of edges
    for e in obj.getEdges():
        if isinstance(e, PartOfEdge) and (e.getNodes()[1] == obj):
            typeOfOther = e.getOther(obj).__class__.__name__.lower()
            typeOfOther += 'es' if typeOfOther.endswith('s') else 's'   #add plural 's' :3
            if typeOfOther in obj.__dict__:
                s = getattr(obj, typeOfOther)
                s.add(e.getOther(obj))
            else:
                setattr(obj, typeOfOther, set([e.getOther(obj)]))
            
            #recursively resolve edges for part-of element
            resolveEdges(e.getOther(obj))

def diff(newConfig, currentConfig):
    """
    Diffs two testbed configurations regarding changed elements. 
    Returns a dictionary containing all mismatching attributes.

    Keyword arguments:
        newConfig -- Configuration-object representing the new configuration to deploy.
        currentConfig -- Configuration-object representing the current state of the testbed.
    """

    #create large diff-dictionary with network/machine ids being the keys

    #current data format for diffs (after frequent changes...)
    #a dictionary for the attributes was used before, but iterating over all attributes is a little less readable then
    #{
    #    "hosts": [
    #        (id1, {'diff': 'new'},
    #        (id2, {'diff': 'changed', further mismatching attributes ...},
    #        (id2, {'diff': 'removed'}
    #    ],
    #   "routers": ...,
    #   "networks": ..., 
    #}
    #
    # 
    #further missmatchign attribute = 'attribute name': { 'diff': 'changed' }
    #or in case of set/list
    #'attribute name': { 'diff': 'changed', 'elements': [(id, { ... their diff ...})] }
    

    diffdict = { "hosts": [], "l2networks": [], "l3networks": [] }

    #add each host of the new config and associate the list of mismatchig attributes
    for h in newConfig.getHosts():
        #see if machine exists
        otherHost = [x for x in currentConfig.getHosts() if x.getGlobalID() == h.getGlobalID()]
        if len(otherHost) > 0:
            otherHost = otherHost[0] #unique name
            diffdict['hosts'].append((h.getGlobalID(), getMismatchingAttr(h, otherHost)))
        else:
            diffdict['hosts'].append((h.getGlobalID(), objectAllNew(h)))

    #look for possibly deleted hosts
    for h in currentConfig.getHosts():
        otherHost = [x for x in newConfig.getHosts() if x.getGlobalID() == h.getGlobalID()]
        if len(otherHost) == 0:
            diffdict['hosts'].append((h.getGlobalID(), objectAllRemoved(h)))   

    #add differences of networks in the newConfig
    for n in newConfig.getL2Networks():
        otherNet = [x for x in currentConfig.getL2Networks() if x.getGlobalID() == n.getGlobalID()]
        if len(otherNet) > 0:
            otherNet = otherNet[0] #unique name
            #if there are changes within the network, all dhcp and dns server have to be changed
            diffdict['l2networks'].append((n.getGlobalID(), getMismatchingAttr(n, otherNet)))
        else:
            diffdict['l2networks'].append((n.getGlobalID(), objectAllNew(n)))

    #look for possibly deleted networks
    for n in currentConfig.getL2Networks():
        otherNet = [x for x in newConfig.getL2Networks() if x.getGlobalID() == n.getGlobalID()]
        if len(otherNet) == 0:
            diffdict['l2networks'].append((n.getGlobalID(), objectAllRemoved(n)))

    #add differences of networks in the newConfig
    for n in newConfig.getL3Networks():
        otherNet = [x for x in currentConfig.getL3Networks() if x.getGlobalID() == n.getGlobalID()]
        if len(otherNet) > 0:
            otherNet = otherNet[0] #unique name
            #if there are changes within the network, all dhcp and dns server have to be changed
            diffdict['l3networks'].append((n.getGlobalID(), getMismatchingAttr(n, otherNet)))
        else:
            diffdict['l3networks'].append((n.getGlobalID(), objectAllNew(n)))

    #look for possibly deleted networks
    for n in currentConfig.getL3Networks():
        otherNet = [x for x in newConfig.getL3Networks() if x.getGlobalID() == n.getGlobalID()]
        if len(otherNet) == 0:
            diffdict['l3networks'].append((n.getGlobalID(), objectAllRemoved(n)))

    return diffdict

def getMismatchingAttr(obj1, obj2):
    """
    Returns a list of missmatching attributes between two objects. Only look at public attributes.

    It works for all primitive. Complex types or lists/sets of those can be compared if their respective __eq__() method is overriden properly.
    Note: lists are ordered and will only match if the included objects are ordered identically, sets are unsorted as their name indicates 

    Keyword arguments:
        obj1 -- the object to compare obj2 to
        obj2 -- the object that will be compared with obj1 
    """

    mismatching = {}
    changes = False #any changes among the attributes?
    #filter private attributes
    for k, v in [k_v2 for k_v2 in list(obj1.__dict__.items()) if not k_v2[0].startswith('_')]:
        #find removed attributes
        for k2, v2 in [k2_v2 for k2_v2 in list(obj2.__dict__.items()) if not k2_v2[0].startswith('_')]:
            if not k2 in obj1.__dict__:
                mismatching[k2] = objectAllRemoved(v2)
                changes = True
        
        #new attributes
        if not k in obj2.__dict__:
            mismatching[k] = objectAllNew(v)
            changes = True
        
        #existing attributes
        else:
            #separate comparison for lists and sets
            if isinstance(v, set) or isinstance(v, frozenset):
                mismatching[k] = getMismatchingAttrSet(v, obj2.__dict__.get(k))
                if mismatching[k]['diff'] == "changed":
                    changes = True
            else:   #primitive types are compared directly
                mismatching[k] = { "diff": "unchanged" if obj2.__dict__.get(k) == v else "changed" }
                if not obj2.__dict__.get(k) == v:
                    changes = True

    if changes:
        mismatching['diff'] = "changed"
    else:
        mismatching['diff'] = "unchanged"

    return mismatching


def getMismatchingAttrSet(set1, set2):
    """
    Returns a dictionary of missmatching objects between two sets, stating the respective attributes. 

    The objects are compared by their ID if they are not primitive. Therefore all lists of elements that will be compared with this method, have to provide a getGlobalID()-method. (Not the best solution, but it solves the case at hand)     

    Keyword arguments:
        set1 -- the set to compare set2's elements to
        set2 -- the set whose elements will be compared with set1 
    """
    mismatching = {}
    mismatching['elements'] = []
    changes = False

    for e1 in set1: #both sets can be empty/shorter/longer than the other one
        if hasattr(e1, 'getGlobalID'):    #verify that all elements have a getGlobalID()-method
            e2 = [x for x in set2 if hasattr(x, 'getGlobalID') and x.getGlobalID() == e1.getGlobalID()]
            if len(e2) > 0:
                e2 = e2[0]
                elementDiff = getMismatchingAttr(e1, e2)
            else:
                elementDiff = objectAllNew(e1)

            if not elementDiff['diff'] == "unchanged":
                changes = True

            mismatching['elements'].append((e1.getGlobalID(), elementDiff))
                
        else:   #if there is no getGlobalID, just compare the sets and return changed/unchanged without further details (can't do any better in this case)
            return { "diff": "unchanged" if set1 == set2 else "changed" } 

    #find removed elements
    for e2 in set2:
        e1 = [x for x in set1 if hasattr(x, 'getGlobalID') and x.getGlobalID() == e2.getGlobalID()]
        if len(e1) == 0:
            mismatching['elements'].append((e2.getGlobalID(), objectAllRemoved(e2)))
            changes = True

    if changes:
        mismatching['diff'] = "changed"
    else:
        mismatching['diff'] = "unchanged"

    return mismatching
    

#Could be alternatively built by calling getMismatchingAttr(None, obj2) and getMismatchingAttr(ob1, None),
#but this would make the function much larger and much more unreadable
def objectAllNew(obj):
    """
    A completely new object/attribute has nothing to be compared to and is therefore quickly built with all new attributes     

    Keyword arguments:
        obj1 -- the new object 
    """
    mismatching = { "diff": "new" }

    if hasattr(obj, '__dict__'):
        for k, v in [k_v for k_v in list(obj.__dict__.items()) if not k_v[0].startswith('_')]:
            mismatching[k] = objectAllNew(v)
    elif (isinstance(obj, set) or isinstance(obj, frozenset)):
        if len(obj) > 0 and hasattr(list(obj)[0], 'getGlobalID'):
            mismatching['elements'] = [(x.getGlobalID(), objectAllNew(x)) for x in obj]
        else:
            mismatching['elements'] = []

    return mismatching

def objectAllRemoved(obj):
    """
    A removed object/attribute has nothing to be compared to and is therefore quickly built with all removed attributes     

    Keyword arguments:
        obj1 -- the removed object 
    """
    mismatching = { "diff": "removed" }

    if hasattr(obj, '__dict__'):
        for k, v in [k_v1 for k_v1 in list(obj.__dict__.items()) if not k_v1[0].startswith('_')]:
            mismatching[k] = objectAllRemoved(v)
    elif (isinstance(obj, set) or isinstance(obj, frozenset)):
        if len(obj) > 0 and hasattr(list(obj)[0], 'getGlobalID'):
            mismatching['elements'] = [(x.getGlobalID(), objectAllRemoved(x)) for x in obj]
        else:
            mismatching['elements'] = []

    return mismatching