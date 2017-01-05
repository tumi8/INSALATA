# INSALATA
IT NetworkS AnaLysis And deploymenT Application

# Quickstart

## Service ##

INSALATA is ideally operated as a systemd service with the following `insalata.service` file in `/etc/systemd/system`:
~~~~
[Unit]
Description=The insalata service for testbed management.

[Service]
Type=simple
ExecStart=<PATH TO startInsalata.py in src directory>

[Install]
WantedBy=multi-user.target
Alias=insalata.service
~~~~

Afterwards you can start, stop and monitor the service using `systemctl`. Note that stopping may take a moment due to forked scanners being joined for a clean termination.
~~~~
systemctl start insalata.service
systemctl status insalata.service
systemctl stop insalata.service
~~~~

To bootstrap the application, the `insalata.conf`, `locations.conf` and the `template` directory from the `config` directory have to be placed into `/etc/insalata`. The `sampleEnvironment` directory provides sample files for scanner configuration and can be used as a reference for custom scanning configuration.

#### insalata.conf ####
Main configuration file for the specification of logging, the port of the service, the location of the planner and all information collection environments. The syntax for specifying environments is included by disabled.

#### locations.conf ####
Specifies locations which are environments to which a deployment can be conducted. Environments have a type, optional information (e.g. connection infos to a hypervisor server), and a list of all available template images for virtual hosts.

#### template directory ####
All scripts (.sh or Ansible playbooks) used by INSALATA during information collection or deployment.

## Additional software ##
INSALATA requires Python 3.5.0+

The location of the planner binary has to be given in the `insalata.conf` to be able to run testbed deployment. The application is currently implemented for use with *fast-downward* which can be obtained [here](http://www.fast-downward.org/ObtainingAndRunningFastDownward).

For deployment and certain information collection modules it is required to [install Ansible](https://docs.ansible.com/ansible/intro_installation.html) (tested with Version 2.1.2.0).

The ZabbixFirewallDump collector module requires the [FFFUU](https://github.com/diekmann/Iptables_Semantics/tree/master/haskell_tool) application to simplify the gathered firewall rules on the management unit. The executable of the tool must be located at `/etc/insalata/template/fffuu/fffuu`.
In addition, this collector module requires an installed Zabbix server. Which data the Zabbix Server must store about the network components is listed in the documentation of the collector module.

The TcpdumpHostCollector collector module requires an installation of [TCPDUMP](http://www.tcpdump.org/tcpdump_man.html) on every device used for collecting.

The NmapService collector module requires [Nmap](https://nmap.org/) installed on the devices used for scanning.



### Python requirements ###
* lxml (3.4.4+)
* configobj (5.0.6+)
* netaddr (0.7.18+)
* paramiko (2.0.2+)
* pysnmp (4.3.2+)

# Documentation
See [ReadTheDocs](https://insalata.readthedocs.io/en/latest/index.html)
