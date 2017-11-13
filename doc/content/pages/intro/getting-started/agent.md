Title: run the Agent
Slug: intro/getting-started/agent


# Run the XXX Agent

After XXX is installed, the agent must be run. At least one server must have a TS and/or KV role, although at least 3 is recommended. A single server deployment is _**highly**_ discouraged
as data loss is inevitable in a failure scenario. [This guide](/docs/guides/bootstrapping.html)
covers bootstrapping a new datacenter. All other agents run health checks,
and forwards queries to servers.

## Starting the Agent

For simplicity, we'll run a single XXX agent in server mode right now:

```
$ /etc/init.d/XXX start

XXX state
YYYYYYYYYYYYYYYYYYYYYYYYYYYY
```

As you can see, the XXX agent has started and has output some log
data. From the log data, you can see that our agent is running in server mode,
and has claimed leadership of the cluster. Additionally, the local member has
been marked as a healthy member of the cluster.


## Cluster Members

If you run `XXX members` in another terminal, you can see the members of
the XXX cluster. You should only see one member (yourself). We'll cover
joining clusters in the next section.

```
$ XXX members
Node                    Address             Status  Type    Build  Protocol
Armons-MacBook-Air      10.1.10.38:8301     alive   server  0.3.0  2
```

The output shows our own node, the address it is running on, its
health state, its role in the cluster.
Additional metadata can be viewed by providing the `-detailed` flag.

The output from the `members` command is generated based on the
[gossip protocol](/docs/internals/gossip.html) and is eventually consistent.

In addition to the HTTP API, the
[DNS interface](/docs/agent/dns.html) can be used to query the node. Note
that you have to make sure to point your DNS lookups to the XXX agent's
DNS server, which runs on port 8600 by default. The format of the DNS
entries (such as "Armons-MacBook-Air.node.XXX") will be covered later.

```
$ dig @127.0.0.1 -p 8600 Armons-MacBook-Air.node.XXX
...

;; QUESTION SECTION:
;Armons-MacBook-Air.node.XXX.	IN	A

;; ANSWER SECTION:
Armons-MacBook-Air.node.XXX.	0 IN	A	10.1.10.38
```

## Stopping the Agent

You can use `Ctrl-C` (the interrupt signal) to gracefully halt the agent.
After interrupting the agent, you should see it leave the cluster gracefully
and shut down.

By gracefully leaving, XXX notifies other cluster members that the
node _left_. If you had forcibly killed the agent process, other members
of the cluster would have detected that the node _failed_. When a member leaves,
its services and checks are removed from the catalog. When a member fails,
its health is simply marked as critical, but is not removed from the catalog.
XXX will automatically try to reconnect to _failed_ nodes, which allows it
to recover from certain network conditions, while _left_ nodes are no longer contacted.

Additionally, if an agent is operating as a server, a graceful leave is important
to avoid causing a potential availability outage affecting the [consensus protocol](/docs/internals/consensus.html).
See the [guides section](/docs/guides/index.html) to safely add and remove servers.

