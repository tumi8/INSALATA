"""
This file contains useful methods for all scanning modules.
"""

from insalata.helper.SSHWrapper import SSHWrapper
from insalata.helper.ansibleWrapper import runAnsibleCommand


def getSSHConnection(host):
    """
    Open SSH Connection to this host.

    Keyword arguments:
        host -- host for connection.

    Return:
        ssh Connection to host; Useable in SSHWrapper
    """
    try:
        ssh = SSHWrapper()
        ssh.connect(host.getID())
        return ssh
    except:
        return None

def releaseSSHConnection(ssh):
    """
    Close SSH Connection to this host.

    Keyword arguments:
        ssh -- Connection to close
    """
    if ssh is not None:
        ssh.close()

def getAnsibleInfo(host):
    """
    Read information from Host using Ansible.

    Keyword arguments:
    host -- Host object to gather information from.
    """
    #First do a ping to get more results
    data = runAnsibleCommand(host.getID(), 'ping')
    if data[0]['status'] == 'UNREACHABLE!':
        return None
    #Get the actual data
    return runAnsibleCommand(host.getID(), 'setup')[0]['json']