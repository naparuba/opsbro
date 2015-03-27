Kunai
======

This is a **preview** of the kunai project about a service discovery / monitoring / light cfg management / command execution tool.

[![Build Status](https://travis-ci.org/naparuba/kunai.svg)](https://travis-ci.org/naparuba/kunai)


Prereqs
========

You will need:

  * python >= 2.6 (but not 3)
  * python-leveldb
  * python-requests
  * python-jinja2 
  * python-cherrypy3
  * python-rsa
  * python-pyasn1




Installation
==============

You need to launch:
   
   python setup.py install


Launch the daemon
=================

You can start kunai as a daemon with:
 
   /etc/init.d/kunai start

You can also launch it in foreground:

   kunai agent start


Terminology
===========

The project terminology is alike Consul one, and is very differtent from Nagios/Shinken one:
  * node: a server where you install the agent (similar to nagios/shinken host)
  * check: something that look for a specific state (OK/WARNING/CRITICAL/UNKNOWN), like CPU, memory or disk space. It's not exported to other hosts  (similar to nagios/shinken services)
  * service: object that expose an important application state to the other nodes (like for example mysql state). It need a check to do the actual check. This data is shared with all others nodes. (no equivalent in nagios/shinken).
 

How to get agent informations (pid, port, state, etc)
=====================================================


Just launch:

   kunai info


Is there an UI available?
=========================

Yes. There is a UI available in the /var/lib/kuani/ui/ directory. It's just flat files and so you can just export the directory with apache/nginx and play with it.


How to add new nodes in the node cluster?
=========================================

First you need to install and launch the node in another server.

Then in this other server you can launch:
  
   kunai join  OTHER-IP


How can I just kunai cluster members?
=====================================

You can list the cluster members on all nodes with :

  kunai  members

And you will see the new node on the UI if you enable it



How to see docker performance informations?
===========================================

If docker is launched on your server, Kunai will get data from it, images and performances.

To list all of this just launch:

  kunai docker stats


How to stop a kunai daemon?
===========================

Just launch:
  
  kunai agent stop


Which checks packs/tags are available?
======================================

Kunai is bundle with some packs, just add them as tag and checks and services will be enable

  * linux
  * debian
  * redis
  * mongodb
  * mysql


