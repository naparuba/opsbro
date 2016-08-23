Kunai
======

This is a **preview** of the kunai project about a service discovery / monitoring / light cfg management / command execution tool.

[![Build Status](https://travis-ci.org/naparuba/kunai.svg)](https://travis-ci.org/naparuba/kunai)


Prereqs
========

You will need:

  * python >= 2.6 (but not 3 currently)
  * python-leveldb
  * python-requests
  * python-jinja2 
  * python-cherrypy3


On linux:

  * sysstat

To monitor mongodb server:

  * python-pymongo



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


How to get agent informations (pid, port, state, etc)
=====================================================


Just launch:

   kunai info


Is there an UI avialable?
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



How to see collected data? (metrology)
======================================

The kunai agent is by default getting lot of metrology data from your OS and applications. It's done by "collctors" objets. You can easily list them and look at the colelcted data by launching:

  kunai collectors show


How to see docker performance informations?
===========================================

If docker is launched on your server, Kunai will get data from it, like colelctors, images and performances.

To list all of this just launch:

  kunai docker stats


How to stop a kunai daemon?
===========================

Just launch:
  
  kunai agent stop



