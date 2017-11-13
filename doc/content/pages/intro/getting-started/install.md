Title: Installing XXXXXX
Slug: intro/getting-started/install


# Install XXX

XXX must first be installed on every node that will be a member of a
XXX cluster. To make installation easy, XXX is provides with [repositories](/downloads.html) for all supported platforms and
architectures. This page will not cover how to install XXX from source.

## Installing XXX

To install XXX, find the [appropriate repository](/downloads.html) for
your system.


## Verifying the Installation

After installing XXX, verify the installation worked by opening a new
terminal session and checking that `XXX` is available. By executing
`XXX` you should see help output similar to that below:

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
    version        Prints the XXX version
```

If you get an error that `XXX` could not be found, then your PATH
environment variable was not setup properly. Please go back and ensure
that your PATH variable contains the directory where XXX was installed.

Otherwise, XXX is installed and ready to go!
