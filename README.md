


This is a first release of the kunai project about a service discovery / monitoring / light cfg management / command execution tool.

[![Build Status](https://travis-ci.org/naparuba/kunai.svg)](https://travis-ci.org/naparuba/kunai)


## **Kunai**: monitoring and service discovery

![Agent](images/agent.png)



## Installation

#### Prerequites
You will need:

  * python >= 2.6 (but not 3 currently)
  * python-leveldb
  * python-requests
  * python-jinja2 
  * python-cherrypy3


To monitor linux:
  * sysstat

To monitor mongodb server:
  * python-pymongo

To monitor mysql server:
  * python-mysql

To monitor redis server:
  * python-redis



#### Installation

Just launch:

    python setup.py install


## Run your daemon, and join the kunai cluster

#### Start Kunai

You can start kunai as a daemon with:
 
    /etc/init.d/kunai start

You can also launch it in foreground:

    kunai agent start


#### Stop kunai daemon
Just launch:
  
    kunai agent stop

Or use the init.d script:

    /etc/init.d/kunai stop



#### Display kunai information
Just launch:

    kunai info

You will have several information about the current kunai agent state:

 
![Agent](images/info.png) 


#### Agent cluster membership

##### Add your local node to the node cluster?

First you need to install and launch the node in another server.

Then in this other server you can launch:
  
    kunai join  OTHER-IP


##### List your kunai cluster members
You can list the cluster members on all nodes with :

    kunai  members

![Agent](images/members.png) 

And you will see the new node on the UI if you enable it





## Discover your server (os, apps, location, ...)

Detectors are rules that are executed by the agent to detect your server properties like

 * OS (linux, redhat, centos, debian, windows, ...)
 * Applications (mongodb, redis, mysql, apache, ...)
 * Location (city, GPS Lat/Long)

You should declare a json object like:

    {
       "detector": {
          "interval": "10s"       
          "apply_if": "grep('centos', '/etc/redhat-release')",               
          "tags": ["linux", "centos"],
       }
    }

 * Execute every 10 seconds
 * If there is the strong centos in the file /etc/redhat-release
 * Then add the tags "linux" and centos" to the local agent


## Collect your server metrics (cpu, kernel, databases metrics, etc)

Collectors are code executed by the agent to grok and store local os or application metrics. 

You can list available collectors with the command:

    kunai collectors list
 
 
![Agent](images/collectors-list.png) 

 * enabled: it's running well
 * disabled: it's missing a librairy for running

## Execute checks

You can execute checks on your agent by two means:
  * Use the collectors data and evaluate check rule on it
  * Execute a nagios-like plugin

### Common check parameters for evaluated and nagios plugins based checks

Some parameters are common on the two check types you can defined.

  * interval: how much seconds the checks will be scheduled
  * apply_on: if present, will declare and execute the check only if the agent tag is present


### Evaluate check rule on collectors data

Evaluated check will use collectors data and should be defined with:
  * ok_output: python expression that create a string that will be shown to the user if the state is OK
  * critical_if: python expression that try to detect a CRITICAL state
  * critical_output: python expression that create a string that will be shown to the user if the state is CRITICAL
  * warning_if: python expression that try to detect WARNING state
  * warning_output: python expression that create a string that will be shown to the user if the state is WARNING
  * thresholds: [optionnal] you can set here dict of thresholds you will access from your check rule by "configuration.thresholds.XXX"
  
The evaluation is done like this:
  * if the critical expression is True => go CRITICAL
  * else if warning expression is True => go WARNING
  * else go OK
  
For example here is a cpu check on a linux server:

     {
        "check": {
            "interval":          "10s",
            "apply_on":          "linux",
            
            "ok_output":         "'OK: cpu is great: %s%%' % (100-{collector.cpustats.cpuall.%idle})",
            
            "critical_if":      "{collector.cpustats.cpuall.%idle} < {configuration.thresholds.cpuidle.critical}",
            "critical_output":  "'Critical: cpu is too high: %s%%' % (100-{collector.cpustats.cpuall.%idle})",

            "warning_if":       "{collector.cpustats.cpuall.%idle} < {configuration.thresholds.cpuidle.warning}",
            "warning_output":   "'Warning: cpu is very high: %s%%' % (100-{collector.cpustats.cpuall.%idle})",
            
            "thresholds" :       {"cpuidle" : { "warning": 5, "critical": 1} }
        }
     }



### Use Nagios plugins

Nagios based checks will use Nagios plugins and run them. Use them if you don't have access to the information you need in the collectors.

The parameter for this is:
  * script: the command line to execute your plugin
  
  Here is an example 
  
      {
             "check": {
                  "apply_on": "linux",
                  "script": "$nagiosplugins$/check_mailq -w $mailq.warning$ -c $mailq.critical$",
                  "interval": "60s",
    
                   "mailq" : {
                      "warning": 1,
                      "critical": 2
                   }
             }
      }
     

NOTE: the $$ evaluation is not matching the previous checks, we will fix it in a future version but it will break the current version configuration.


## Notify check/node state change with emails

// Handlers

## Export your nodes and check states into Shinken

You can export all your nodes informations (new, deleted or change node) into your Shinken installation. It will automatically:
  * create new host when you start a new node
  * change the host configuration (host templates) when a new tag is add/removed on your agent
  * remove your host when you delete your agent (by terminating your Cloud instance for example)

You must add in the agent installed on your shinken arbiter daemon the following local configuration:

     {
         "shinken": {
             "cfg_path": "/etc/shinken/agent"
         }
     }

  * cfg_path: a directory where all your nodes will be sync as shinken hosts configuration (cfg files)

Currently it also use hard path to manage your shinken communication:
  * the unix socket */var/lib/shinken/nagios.cmd* should be created by your shinken arbiter/receiver [named-pipe](http://shinken.io/package/named-pipe) module.
  * it call the "/etc/init.d/shinken reload" command when a node configuration is changed(new, removed or tag/template change) 


## Access your nodes informations by DNS

If you enable the DNS interface for your agent, it will start an internal DNS server that will answer to queries. So your applications will be able to easily exchange with the valid node that is still alive or launched.

You must define a dns object in your local configuration to enable this interface:

    {
        "dns":{
	        "enabled"    : true,
	        "port"       : 6766,
	        "domain"     : ".kunai"
        }    
    }

  * enabled: start or not the listener
  * port: UDP port to listen for UDP requests
  * domain: allowed domain to request, should match a specific domain name to be redirected to this 

You will be able to query it with dig for test:

    $dig -p 6766 @localhost redis.tag.dc1.kunai  +short
    192.168.56.103
    192.168.56.105

TODO: document the local dns redirect to link into resolv.conf


## Export and store your application telemetry into the agent metric system 

// statsd & graphite

**TODO**: change the ts tag that enable this feature to real *role*


## Get access to your graphite data with an external UI like Grafana



## Get notified when there is a node change (websocket)

You can get notified about a node change (new node, deleted node or new tag or check state change) with a websocket interface on your local agent.

All you need is to enable it on your local node configuration:

    {
        "websocket": {
	        "enabled"    : true,
	        "port"       : 6769
        }
    }

  * enabled: start or not the websocket listener
  * port: which TCP port to listen for the websocket connections
  
**Note**: the HTTP UI need the websocket listener to be launched to access node states.

## Store your data/configuration into the cluster (KV store)

// KV Store


**TODO**: change the KV store from tag to a role

## Use your node states and data/configuration (KV) to keep your application configuration up-to-date

// Generators


## How to see collected data? (metrology)

The kunai agent is by default getting lot of metrology data from your OS and applications. It's done by "collctors" objets. You can easily list them and look at the colelcted data by launching:

    kunai collectors show


**TODO** Allow to export into json format


## How to see docker performance informations?

If docker is launched on your server, Kunai will get data from it, like collectors, images and performances.

To list all of this just launch:

    kunai docker show


## Get Quorum strong master/slave elections thanks to RAFT
  
You can ask your node cluster system to elect a node for a specific task or application thanks to the RAFT implementation inside the agents

**TODO**: currently in alpha stade in the code   


## Access the agent API documentation

**TODO**: this must be developed, in order to access your node API available in text or HTTP


## Is there an UI available?

Yes. There is a UI available in the */var/lib/kunai/ui/* directory. It's just flat files and so you can just export the directory with apache/nginx and play with it.

