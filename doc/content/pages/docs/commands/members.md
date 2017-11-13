Title: Commands: Members
Slug: docs/commands/members
Part: docs

# XXX Members

Command: `XXX members`

The members command outputs the current list of members that a XXX
agent knows about, along with their state. The state of a node can only
be "alive", "left", or "failed".

Nodes in the "failed" state are still listed because XXX attempts to
reconnect with failed nodes for a certain amount of time in the case
that the failure is actually just a network partition.

## Usage

Usage: `XXX members [options]`

The command-line flags are all optional. The list of available flags are:

* `-detailed` - If provided, output shows more detailed information
  about each node.

* `-rpc-addr` - Address to the RPC server of the agent you want to contact
  to send this command. If this isn't specified, the command will contact
  "127.0.0.1:8400 " which is the default RPC address of a XXX agent.

* `-status` - If provided, output is filtered to only nodes matching
  the regular expression for status

* `-wan` - For agents in Server mode, this will return the list of nodes
  in the WAN gossip pool. These are generally all the server nodes in
  each datacenter.

