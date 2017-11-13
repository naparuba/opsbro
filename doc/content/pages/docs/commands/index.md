Title: Commands
Slug: docs/commands/index


# XXX Commands (CLI)

XXX is controlled via a very easy to use command-line interface (CLI).
XXX is only a single command-line application: `XXX`. This application
then takes a subcommand such as "agent" or "members". The complete list of
subcommands is in the navigation to the left.

The `XXX` CLI is a well-behaved command line application. In erroneous
cases, a non-zero exit status will be returned. It also responds to `-h` and `--help`
as you'd most likely expect. And some commands that expect input accept
"-" as a parameter to tell XXX to read the input from stdin.

To view a list of the available commands at any time, just run `XXX` with
no arguments:

```
$ XXX
usage: XXX [--version] [--help] <command> [<args>]

Available commands are:
    agent          Runs a XXX agent
    force-leave    Forces a member of the cluster to enter the "left" state
    info           Provides debugging information for operators
    join           Tell XXX agent to join cluster
    keygen         Generates a new encryption key
    leave          Gracefully leaves the XXX cluster and shuts down
    members        Lists the members of a XXX cluster
    monitor        Stream logs from a XXX agent
    reload         Triggers the agent to reload configuration files
    version        Prints the XXX version
```

To get help for any specific command, pass the `-h` flag to the relevant
subcommand. For example, to see help about the `join` subcommand:

```
$ XXX join -h
Usage: XXX join [options] address ...

  Tells a running XXX agent (with "XXX agent") to join the cluster
  by specifying at least one existing member.

Options:

  -rpc-addr=127.0.0.1:8400  RPC address of the XXX agent.
  -wan                      Joins a server to another server in the WAN pool

```
