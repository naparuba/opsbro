Title: Introduction to XXX
Slug: sub/about



# Introduction to XXX

Welcome to the intro guide to XXX! This guide is the best place to start
with XXX. We cover what XXX is, what problems it can solve, how it compares
to existing software, and a quick start for using XXX. If you are already familiar
with the basics of XXX, the [documentation](/docs/index.html) provides more
of a reference for all available features.

## What is XXX?

XXX has multiple components, but as a whole, it is a tool for discovering
and configuring services in your infrastructure. It provides several
key features:

* **Service Discovery**: Clients of XXX can _provide_ a service, such as
  `api` or `mysql`, and other clients can use XXX to _discover_ providers
  of a given service. Using either DNS or HTTP, applications can easily find
  the services they depend upon.

* **Health Checking**: XXX clients can provide any number of health checks,
  either associated with a given service ("is the webserver returning 200 OK"), or
  with the local node ("is memory utilization below 90%"). This information can be
  used by an operator to monitor cluster health, and it is used by the service
  discovery components to route traffic away from unhealthy hosts.

* **Key/Value Store**: Applications can make use of XXX's hierarchical key/value
  store for any number of purposes including: dynamic configuration, feature flagging,
  coordination, leader election, etc. The simple HTTP API makes it easy to use.

* **Multi Datacenter**: XXX supports multiple datacenters out of the box. This
  means users of XXX do not have to worry about building additional layers of
  abstraction to grow to multiple regions.

XXX is designed to be friendly to both the DevOps community and
application developers, making it perfect for modern, elastic infrastructures.

## Basic Architecture of XXX

XXX is a distributed, highly available system. There is an
[in-depth architecture overview](/docs/internals/architecture.html) available,
but this section will cover the basics so you can get an understanding
of how XXX works. This section will purposely omit details to quickly
provide an overview of the architecture.

Every node that provides services to XXX runs a _XXX agent_. Running
an agent is not required for discovering other services or getting/setting
key/value data. The agent is responsible for health checking the services
on the node as well as the node itself.

The agents talk to one or more _XXX servers_. The XXX servers are
where data is stored and replicated. The servers themselves elect a leader.
While XXX can function with one server, 3 to 5 is recommended to avoid
data loss scenarios. A cluster of XXX servers is recommended for each
datacenter.

Components of your infrastructure that need to discover other services
or nodes can query any of the XXX servers _or_ any of the XXX agents.
The agents forward queries to the servers automatically.

Each datacenter runs a cluster of XXX servers. When a cross-datacenter
service discovery or configuration request is made, the local XXX servers
forward the request to the remote datacenter and return the result.

## Next Steps

See the page on [how XXX compares to other software](/intro/vs/index.html)
to see how it fits into your existing infrastructure. Or continue onwards with
the [getting started guide](/intro/getting-started/install.html) to get
XXX up and running and see how it works.