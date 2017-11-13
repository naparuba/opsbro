Title: Introduction to XXX
Slug: intro/index
Part: intro

# Introduction to XXX

Welcome to the intro guide to XXX! In this guide we will what XXX is, what problems it can solve for you, how it compares to your existing software, and a quick start for using XXX. If you are already familiar with XXX, the [documentation](/docs/index.html) provides more of a reference for all available features.

## What is XXX?

XXX has multiple components, but as a whole, it is a tool for discovering
and monitoring services in your infrastructure. It provides several
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

* **Metrology**: XXX clients can export metrics and retrive them for a long perdiod of time. 
  Clients can send metrics by both [graphite](https://github.com/graphite-project) or [statsd](https://github.com/etsy/statsd) formats.


* **Key/Value Store**: Applications can make use of XXX's hierarchical key/value
  store for any number of purposes including: dynamic configuration, feature flagging, etc
  The simple HTTP API makes it easy to use.

* **Distributed command execution**: XXX can help you to run distributed commands on all your nodes or just some of them with a specific role.

XXX is designed to be match both the DevOps and application developers. It make their life easiers to build elastic infrastructures.

## Basic Architecture of XXX

XXX is a distributed, highly available system. There is an
[in-depth architecture overview](/docs/internals/architecture.html) available,
but this section will cover the basics so you can get an understanding
of how XXX works. This section will purposely omit details to quickly
provide an overview of the architecture.

Every node that provides services or you want to monitor must run XXX. Running a daemon for discovering other services or getting/setting key/value data. The daemon is responsible for health checking the services on the node as well as the node itself.

Some agents can have some specific roles used by the XXX cluster. Such roles are:

* **KV**: manage the data retention for the _key store_ feature

* **TS**: manage listening port for the _time series/metrology_ feature

Such agent will be named **core nodes**.

For each feature the cluster manage to distribute and replicate the data accross the nodes. One agent can run both roles. 
While each role can be manage with one server, 3 to 5 is recommended to avoid
data loss scenarios. A cluster of XXX servers for each role is recommended for each
datacenter.

Components of your infrastructure that need to discover other services
or nodes can query any of the XXX node.

## Next Steps

See the page on [how XXX compares to other software](/intro/vs/index.html)
to see how it fits into your existing infrastructure. Or continue onwards with
the [getting started guide](/intro/getting-started/install.html) to get
XXX up and running and see how it works.
