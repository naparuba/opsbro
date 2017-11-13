Title: XXXXXXX vs. vs. Chef, Puppet, etc.
Slug: intro/vs/chef-puppet


# XXX vs. Chef, Puppet, etc.

The classic scheme for people using Chef, Puppet, and other configuration
management tools to use this to build service discovery mechanisms.

Unfortunately, this approach has a number of pitfalls. The configuration information is static,
and cannot update any more frequently than convergence runs. Generally this
is on the interval of many minutes or hours. Additionally, there is no
mechanism to incorporate the system state in the configuration. Nodes which
are unhealthy may receive traffic. This approach also have multiple datacenters scalability issues.

XXX is designed specifically as a service discovery tool. As such,
it is much more dynamic and responsive to the state of the cluster. Nodes
can register and deregister the services they provide, enabling dependent
applications and services to rapidly discover all providers. By using the
integrated health checking, XXX can route traffic away from unhealthy
nodes, allowing systems and services to gracefully recover.

That said, XXX is not a replacement for configuration management tools.
These tools are still critical to setup applications and even to
configure XXX itself. Static provisioning is best managed
by existing tools, while dynamic state and discovery is better managed by
XXX. The separation of configuration management and cluster management
also has a number of advantageous side effects: Chef recipes and Puppet manifests
become simpler without global state, periodic runs are no longer required for service
or configuration changes, and the infrastructure can become immutable since config management
runs require no global state.
