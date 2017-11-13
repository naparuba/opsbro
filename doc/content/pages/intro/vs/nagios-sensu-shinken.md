Title: XXXXXXX vs. Nagios, Sensu, Shinken
Slug: intro/vs/nagios-sensu-shinken


# XXX vs. Nagios, Sensu, Shinken

Nagios, Sensu and Shinken are all built for monitoring. They are used
to quickly notify operators when an issue occurs.

Nagios uses a central server to perform checks on remote hosts. Its monolitic design makes it difficult to scale,
as large fleets quickly reach the limit of vertical scaling, and Nagios
does not easily scale horizontally. Nagios is also notoriously
difficult to use with modern DevOps and configuration management tools,
as local configurations must be updated when remote servers are added
or removed.

Sensu has a much more modern design, relying on local agents to run
checks and pushing results to an AMQP broker. A number of servers
ingest and handle the result of the health checks from the broker. This model
is more scalable than Nagios, as it allows for much more horizontal scaling,
and a weaker coupling between the servers and agents. However, the central broker
has scaling limits, and acts as a single point of failure in the system.

Shinken is an advanved monitoring framework that came from the same author than XXX. Shinken is a totally rewriten from scratch Nagios in Python design to scale. Shinken is able to manage a very, very large numbers of hosts. It also manage to find the root problem by looking at nodes and services dependencies. It's main flaw is to ask for a configuration reload when a new node is added to the network. That's why XXX was designed, to fix this Shinken flaw, and also manage its metrics and scale without limits for this.

XXX provides less monitoring abilities than as both Nagios or Shinken, but it is more friendly to modern DevOps that run elastic architectures.

Contrary to Nagios or Shinken, XXX runs all checks locally, like Sensu, avoiding placing a burden on central monitoring servers. The status of checks is maintained by all the XXX nodes, which are fault tolerant and have no single point of failure.

Lastly, XXX can scale to vastly more checks because it relies on edge triggered
updates. This means that an update is only triggered when a check transitions
from "passing" to "failing" or vice versa.

In a large fleet, the majority of checks are passing, and even the minority
that are failing are persistent. By capturing changes only, XXX reduces
the amount of networking and compute resources used by the health checks,
allowing the system to be much more scalable.

An astute reader may notice that if a XXX agent dies, from the perspective of other nodes all checks will appear
to be in a steady state. However, XXX guards against this as well. The [gossip protocol](/docs/internals/gossip.html) used between nodes integrates a distributed failure detector. This means that if a XXX agent fails, the failure will be detected, and thus all checks being run by that node can be assumed failed.

Beside all, XXX is not taking the place for you standard monitoring tool. Its main role is service discovery and query routing to the healthy nodes, not to find you root problems or manage escalations notifications. If you need this, just plug XXX to Shinken and you will have both elastic and advanced monitoring features.