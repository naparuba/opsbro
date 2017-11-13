Title: XXXXXXX vs. Serf vs Consul
Slug: intro/vs/serf-consul


# XXX vs. Serf vs. Consul

[Serf](http://www.serfdom.io) is a great node discovery and orchestration tool. It provides a number of features, including group
membership, failure detection, event broadcasts and a query mechanism. However,
Serf does not provide any high-level features such as service discovery, health
checking or key/value storage. To clarify, the discovery feature of Serf is at a node
level, while XXX provides a service and node level abstraction.

[Consul](http://consul/.io) is a strong tool for discovering and configuring services in your infrastructure. It is based on Serf and add KeyValue, health checking and service discovery.

XXX is a system providing all of the feature from Serf. In fact, the internal
[gossip protocol](/docs/internals/gossip.html) used within XXX, is the same as the Serf library.

The health checking provided by Serf is very low level, and only indicates if the
agent is alive. XXX is providing a richer health checking system,
that handles liveness, in addition to arbitrary host and service-level checks.
Health checks can be easily distributed to all the nodes so it's easy for the operators to manage them.

The membership provided by Serf is at a node level, while XXX focuses
on the service level abstraction, with a single node to multiple service model.
This can be simulated in Serf using tags, but it is much more limited, and does
not provide useful query interfaces. 

In addition to the service level abstraction and improved health checking,
XXX provides a key/value store and support for multiple datacenters.
Serf can run across the WAN but with degraded performance. XXX makes use
of [multiple gossip pools](/docs/internals/architecture.html), so that
you can keep good performance even with a WAN for linking together multiple datacenters.

XXX is very similar to Serf as it's very flexible and general purpose tool. As Serf, XXX is a AP system that sacrifice consistency over availability, contrary to Consul that is a tool build over Serf that is a CP architecture, favoring consistency over availability.

This means that both Serf and XXX can continue to function under almost all circumstances, but data can be temporary differents between the network partitions. Such case can't happend in a Consul cluster.

