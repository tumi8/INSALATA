# This decorator can be used for all functions inside the insalata.builder namespace in order to declare a function 
# as suitable for being used during the automed setup process to execute a certain action for either a certain
# hypervisor/template metadata/service or multiple of those.
# A suitable function is automatically determined during the setup which helps to avoid large mapping/config files
# in case new functionality is added.  

def builderFor(action, hypervisor=None, template=None, service=None):
    """
    This decorator is used to supply metadata for functions which is then used to find suitable methods
    during building just by these properties.

    :param action: Name of the generic step/action (see planner) that this function implements 
    :type action: str

    :param hypervisor: Name of the hypervisor that this function can be used for
    :type action: str

    :param template: A list of template properties this function is suitable for (e.g. OS, certain software) 
    :type action: [str]

    :param service: Production or type of the service that this function can be used for
    :type action: str

    :returns: The deocorated input function with the given attribute values
    :rtype: function
    """
    def decorate(f):
        f.action = action
        f.hypervisor = hypervisor
        f.template = template
        f.service = service
        return f
    return decorate