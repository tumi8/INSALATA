(define (domain testbed)
  (:requirements :strips :equality :typing :conditional-effects :action-costs)
  (:types router - host plain - host host network interface dhcp - service dns - service service disk)
  (:predicates (named ?x - host)
              (nameNotApplied ?x) 
              (created ?x)
              (running ?x - host)
              (old ?x)
              (new ?x)
              
              (cpusConfigured ?x - host)
              (memoryConfigured ?x - host)
              (templateChanged ?x - host)
              
              (dnsConfigured ?x - dns)
              (dhcpConfigured ?x - dhcp)
              (serviceConfigured ?x - service)
              (routingConfigured ?x - router)
              (firewallConfigured ?x - host)
              
              (networkConfigured ?x - interface)
              (mtuConfigured ?x - interface)
              (rateConfigured ?x - interface)
              (interfaceConfigured ?x - interface)
              (static ?x - interface)

              (attached ?d - disk ?h - host)

              (part-of ?x ?y)

              (configNameAdded ?x)
  )

  (:functions (total-cost) - number)

  ;create a network without any preconditions
  (:action createNetwork
  :parameters (?n - network)
  :precondition (not (created ?n))
  :effect (and (created ?n) (increase (total-cost) 1)))

  ;named machines can be booted without any further consideration
  (:action boot
  :parameters (?x - host)
  :precondition (and (created ?x) (not (running ?x)) (named ?x) (not (nameNotApplied ?x)))
  :effect (and (running ?x) (increase (total-cost) 5)))

  ;boot a machine whose name has changed since the last reboot and therefore the hostname change is now taking effect
  (:action bootAndNamed
  :parameters (?x - host)
  :precondition (and (created ?x) (not (running ?x)) (named ?x) (nameNotApplied ?x))
  :effect (and (running ?x) (not (nameNotApplied ?x)) (increase (total-cost) 5)))

  ;boot a machine who hasn't been renamed
  ;only one unnamed machine is allowed to be booted at a certain point in time
  (:action bootUnnamed
  :parameters (?x - plain)
  :precondition (and (created ?x) (not (running ?x)) (forall (?p - plain) (imply (or (not (named ?p)) (nameNotApplied ?p)) (not (running ?p))))) 
  :effect (and (running ?x) (increase (total-cost) 5)))

  (:action bootUnnamed
  :parameters (?x - router)
  :precondition (and (created ?x) (not (running ?x)) (forall (?r - router) (imply (or (not (named ?r)) (nameNotApplied ?r)) (not (running ?r))))) 
  :effect (and (running ?x) (increase (total-cost) 5)))

  (:action shutdown
  :parameters (?x - host)
  :precondition (running ?x)
  :effect (and (not (running ?x)) (increase (total-cost) 2)))

  (:action reboot
  :parameters (?x - host)
  :precondition (running ?x)
  :effect (and (running ?x) (increase (total-cost) 5)))

  (:action rebootAndNamed
  :parameters (?x - host)
  :precondition (and (running ?x) (nameNotApplied ?x))
  :effect (and (running ?x) (not (nameNotApplied ?x)) (increase (total-cost) 5)))

  ;create all hosts (plain and router)
  ;todo: check if maybe old machines break the precondition
  (:action createHost
  :parameters (?x - host)
  :precondition (and 
      (not (created ?x)) 
    )
  :effect (and 
    (created ?x)
    (cpusConfigured ?x) 
    (memoryConfigured ?x)
    (increase (total-cost) 10))
  )

  ;create interfaces if the machine this interface is part of has been created
  (:action createInterface
  :parameters (?x - interface)
  :precondition (and 
    (not (created ?x))
    (forall (?h - host) 
      (imply (part-of ?x ?h) (and (created ?h) (not (running ?h))))
    )
    (forall (?n - network) 
      (imply (part-of ?x ?n) (created ?n))
    )
  )
  :effect (and
    (created ?x) 
    (networkConfigured ?x) 
    (mtuConfigured ?x)
    (rateConfigured ?x)
    (increase (total-cost) 1))
  )

  ;force deletion of a host (this is the only way to get rid of a 'templateChanged' predicate)
  (:action deleteHost
  :parameters (?h - host)
  :precondition (and 
    (created ?h) 
    (not (running ?h)))
  :effect (and 
    (not (created ?h)) 
    (not (named ?h)) 
    (not (templateChanged ?h))
    (not (configNameAdded ?h))
    (forall (?i - interface) 
      (and 
        (when (part-of ?i ?h) (and (not (created ?i)) (not (interfaceConfigured ?i))))
        (forall (?s - service) 
          (when (part-of ?s ?i) 
          (and 
            (not (created ?s)) 
            (not (dnsConfigured ?s)) 
            (not (dhcpConfigured ?s)) 
            (not (serviceConfigured ?s))
          ))
        )
      )
    )
    (increase (total-cost) 10))
  )

  ;delete a network from the system 
  (:action removeNetwork
  :parameters (?n - network)
  :precondition (and
      (old ?n)
      (forall (?i - interface) (imply (part-of ?i ?n) (not (created ?i))))
    )
  :effect (and (not (created ?n)) (increase (total-cost) 1)))

  ;delete a host from the system
  (:action removeHost
  :parameters (?h - host)
  :precondition (and 
    (old ?h) 
    (not (running ?h)))
  :effect (and 
    (not (created ?h))
    (forall (?i - interface)
      (when (part-of ?i ?h) (and 
        (not (created ?i)) 
    ;    (not (interfaceConfigured ?i))
    ;    (not (mtuConfigured ?i)) 
    ;    (not (rateConfigured ?i)) 
    ;    (not (networkConfigured ?i))
      ))
    )
    (increase (total-cost) 1)
  ))

  ;add (or create if it doesn't exist) a disk to a host
  (:action addDisk
  :parameters (?d - disk ?h - host)
  :precondition (and
    (created ?h)
    (not (attached ?d ?h))
    (part-of ?d ?h)
  )
  :effect (and (attached ?d ?h) (increase (total-cost) 1)))

  ;add (or create if it doesn't exist) a disk to a host
  (:action removeDisk
  :parameters (?d - disk ?h - host)
  :precondition (and
    (old ?d)
    (attached ?d ?h)
  )
  :effect (and (not (attached ?d ?h)) (increase (total-cost) 1)))

  ;delete an interface from the system
  (:action removeInterface
  :parameters (?i - interface)
  :precondition (and 
    (old ?i)
    (forall (?h - host) (imply (part-of ?i ?h) (not (running ?h))))
  )
  :effect (and 
    (not (created ?i)) 
    (not (mtuConfigured ?i)) 
    (not (rateConfigured ?i)) 
    (not (networkConfigured ?i))
    (increase (total-cost) 1)
  ))

  ;assign a hostname if the host has been created and is up and running
  (:action name
  :parameters (?x - host)
  :precondition (running ?x)
  :effect (and (named ?x) (nameNotApplied ?x) (increase (total-cost) 1)))

  ;setup routing once all interfaces of a router are configured
  (:action configureRouting
  :parameters (?r - router)
  :precondition (and 
    (running ?r)
    (forall (?i - interface) 
      (imply (part-of ?i ?r) (interfaceConfigured ?i))
    )
  )
  :effect (and (routingConfigured ?r) (increase (total-cost) 1)))

  ;setup firewall once all interfaces of a host are configured
  (:action configureFirewall
  :parameters (?h - host)
  :precondition (and 
    (running ?h)
    (forall (?i - interface) 
      (imply (part-of ?i ?h) (interfaceConfigured ?i))
    )
  )
  :effect (and (firewallConfigured ?h) (increase (total-cost) 1)))

  ;set virtual cpus on halted machine
  (:action configureCpus
  :parameters (?x - host)
  :precondition (and 
    (created ?x) 
    (not (running ?x)))
  :effect (and (cpusConfigured ?x) (increase (total-cost) 1)))

  ;set memory on halted machine
  (:action configureMemory
  :parameters (?x - host)
  :precondition (and 
    (created ?x) 
    (not (running ?x)))
  :effect (and (memoryConfigured ?x) (increase (total-cost) 1)))

  ;configure interfaces on a host if all interfaces have been created and all servers have dhcp/dns configured
  (:action configureInterface
  :parameters (?x - interface)
  :precondition (and 
    (created ?x)
    (forall (?h - host) (imply (part-of ?x ?h) (running ?h))) 
    (networkConfigured ?x) 
    (rateConfigured ?x) 
    (mtuConfigured ?x)
    (forall (?d - dns) (dnsConfigured ?d))
    (forall (?d - dhcp) (dhcpConfigured ?d))
  )
  :effect (and (interfaceConfigured ?x) (increase (total-cost) 1)))

  ;configure interfaces on a host if it is static and doesn't have to wait for dns or dhcp
  (:action configureInterface
  :parameters (?x - interface)
  :precondition (and 
    (created ?x)
    (forall (?h - host) (imply (part-of ?x ?h) (running ?h))) 
    (networkConfigured ?x) 
    (rateConfigured ?x) 
    (mtuConfigured ?x)
    (static ?x)
  )
  :effect (and (interfaceConfigured ?x) (increase (total-cost) 1)))

  ;remove the configuration of an interfaces on a host
  (:action unconfigureInterface
  :parameters (?x - interface)
  :precondition (and 
    (not (created ?x))
    (interfaceConfigured ?x)
    (old ?x)
    (forall (?h - host) (imply (part-of ?x ?h) (running ?h))) 
  )
  :effect (and 
    (not (interfaceConfigured ?x)) 
    (forall (?h - host) 
      (when (part-of ?i ?h) (not (part-of ?i ?h)))
    )
    (increase (total-cost) 1)
  ))

  ;configure DNS on a DNS server if all interfaces of it are configured
  (:action configureDns
  :parameters (?s - dns)
  :precondition (and 
    (not (dnsConfigured ?s))
    (forall (?i - interface) 
      (imply (part-of ?s ?i) 
        (and 
          (created ?i) 
          (interfaceConfigured ?i)
          (forall (?h - host)
            (imply (part-of ?i ?h) (and (created ?h) (named ?h) (running ?h)))
          )
        )
      )
    )
  ) 
  :effect (and (created ?s) (not (new ?s)) (dnsConfigured ?s) (serviceConfigured ?s) (increase (total-cost) 1)
    (forall (?d - dns)
      (when (new ?s) (and (not (dnsConfigured ?d)) (not (new ?d))))
    )
  ))

  ;remove a DNS server configuration
  (:action unconfigureDns
  :parameters (?s - dns)
  :precondition (old ?s)
  :effect (and (not (created ?s)) (not (dnsConfigured ?s)) (not (serviceConfigured ?s)) (increase (total-cost) 1)))

  ;configure DHCP on a DHCP server if all interfaces of it are configured
  (:action configureDhcp
  :parameters (?s - dhcp)
  :precondition (and 
    (not (dhcpConfigured ?s))
    (forall (?i - interface) 
      (imply (part-of ?s ?i) 
        (and 
          (created ?i)
          (interfaceConfigured ?i)
          (forall (?h - host)
            (imply (part-of ?i ?h) (and (created ?h) (named ?h) (running ?h)))
          )
        )
      )
    )
  ) 
  :effect (and (created ?s) (dhcpConfigured ?s) (serviceConfigured ?s) (increase (total-cost) 1)))

  ;remove a DHCP server configuration
  (:action unconfigureDhcp
  :parameters (?s - dhcp)
  :precondition (old ?s)
  :effect (and (not (created ?s)) (not (dnsConfigured ?s)) (not (serviceConfigured ?s)) (increase (total-cost) 1)))

  ;hardware configuration of interfaces (setting network, MAC-address and a bandwidth limit (rate))
  (:action configureNetwork
  :parameters (?x - interface)
  :precondition (and (created ?x) (forall (?h - host) (imply (part-of ?x ?h) (not (running ?h)))) (forall (?d - dhcp) (dhcpConfigured ?d)))
  :effect (and (networkConfigured ?x) (increase (total-cost) 1)))

  (:action configureMtu
  :parameters (?x - interface)
  :precondition (created ?x)
  :effect (and (mtuConfigured ?x) (increase (total-cost) 1)))

  (:action configureRate
  :parameters (?x - interface)
  :precondition (created ?x)
  :effect (and (rateConfigured ?x) (increase (total-cost) 1)))

  ;add name of the config to the host/network/disk for future scanning
  (:action addConfigNameNetwork
  :parameters (?x - network)
  :precondition (and 
    (created ?x)
    (not (old ?x))
  )
  :effect (and (configNameAdded ?x) (increase (total-cost) 1)))

  (:action addConfigNameHost
  :parameters (?x - host)
  :precondition (and 
    (created ?x)
    (not (old ?x))
  )
  :effect (and (configNameAdded ?x) (increase (total-cost) 1)))

  (:action addConfigNameDisk
  :parameters (?x - disk)
  :precondition (and 
    (created ?x)
    (not (old ?x))
  )
  :effect (and (configNameAdded ?x) (increase (total-cost) 1)))
)
