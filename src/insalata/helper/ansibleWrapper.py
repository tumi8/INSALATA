import json
import subprocess
import re
import sys

def addToKnownHosts(hostname):
    """
    Sets all hosts given in hostlist as hosts known to Ansible by editing the /etc/ansible/hosts

    :param hostname: A hostname to add to the list of known hosts for ansible
    :type hostname: str
    """
    #run with json
    subprocess.call('ansible-playbook /etc/insalata/template/ansible/host.yml --extra-vars "host={0}"'.format(hostname), shell=True)

#Run an arbitrary ansible adhoc command
def runAnsibleCommand(host, module):
    addToKnownHosts(host)
    process = subprocess.Popen(["ansible", host, "-m", module], stdout=subprocess.PIPE)
    output = process.communicate()[0]

    return parseAnsibleCommand(output.decode(sys.stdout.encoding))

#return the json from an ansible module output
def parseAnsibleCommand(out):
    hosts = list()
    out = out.replace("\n}\n", "}--")
    out = out.replace("\n", "")
    hostReturns = re.findall('.*?{.*?}--', out)
    for host in hostReturns:
        host = host.replace("}--", "}")
        val = re.split(' \| | => ', host)
        hosts.append({'host': val[0], 'status': val[1], 'json': json.loads(val[2])})

    return hosts

def copyFile(user, filename):
    subprocess.call(["ansible " + "user " + "-m copy " + "-a " + "src=" +filename + "dest=. mode=744"], shell=True)