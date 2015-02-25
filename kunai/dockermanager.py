#!/usr/bin/env python
import json
import time
import sys

from kunai.stats import STATS
from kunai.log import logger
from kunai.threadmgr import threader
from kunai.now import NOW
from kunai.httpdaemon import route, response
from kunai.cgroups import cgroupmgr
from kunai.unixclient import get_json, request_errors


def lower_dict(d):    
    nd = {}
    for k,v in d.iteritems():
        nk = k.lower()
        if isinstance(v, dict): # yes, it's recursive :)
            v = lower_dict(v)
        nd[nk] = v
    return nd




class DockerManager(object):
    def __init__(self):
        self.con = None
        self.containers = {}
        self.images = {}
        # We got an object, we can fill the http daemon part
        self.export_http()
        # last stats computation for containers, some are rate
        # we must compare
        self.stats = {}
        self.last_stats = 0
        # We also aggregate stats to the images level
        self.images_stats = {}

        
    def get_info(self):
        r = {'enabled':     True, #TODO: manage in the configuration in a global way
             'connected' :  self.con is not None,
             'containers':  self.containers,
             'version'   : '',
             'api'       : '',
             'images'    : self.images,
        }
        if self.con:
            r['version'] = self.con['Version']
            r['api'] = self.con['ApiVersion']
            
        return r


    def get_stats(self):
        r = {'containers': self.stats,
             'images'    : self.images_stats,
            }
        return r
    
        
    def launch(self):
        t = threader.create_and_launch(self.do_loop, name='docker-loop')
        t = threader.create_and_launch(self.do_stats_loop, name='docker-stats-loop')        
        

    def connect(self):
        if not self.con:
            try:
                self.con = get_json('/version', local_socket='/var/run/docker.sock')
            except request_errors, exp: # cannot connect
                self.con = None
                logger.debug('Cannot connect to docker')
                return
            # Version return something like this:
            #{
            #    "ApiVersion":"1.12",
            #    "Version":"0.2.2",
            #    "GitCommit":"5a2a5cc+CHANGES",
            #    "GoVersion":"go1.0.3"
            #        }
            if self.con == '':
                self.con = None
                logger.debug('Cannot connect to docker')


    def load_container(self, _id):
        try:
            inspect = get_json('/containers/%s/json' % _id, local_socket='/var/run/docker.sock')
        except request_errors, exp:
            self.connect()
            return
        c = lower_dict(inspect)
        logger.debug('LOADED NEW CONTAINER %s' % c)
        self.containers[_id] = c
        
    
    def load_containers(self):
        if not self.con:
            return
        try:
            conts = get_json('/containers/json', local_socket='/var/run/docker.sock')
        except request_errors, exp:
            self.connect()
            return
            
        for c in conts:
            _id = c.get('Id')
            self.load_container(_id)
            logger.info("Loading docker container %s" % _id)
            logger.debug("Container data", self.containers[_id])

            
    def load_images(self):
        if not self.con:
            return
        try:
            self.images = get_json('/images/json', local_socket='/var/run/docker.sock')
        except request_errors, exp:
            self.connect()
            return
            

        
    def compute_stats(self):
        cids = self.containers.keys()
        stats = cgroupmgr.get_containers_metrics(cids)

        now = time.time()
        for (cid, nst) in stats.iteritems():
            c_stats = self.stats.get(cid, {})
            if self.last_stats != 0:
                diff = now - self.last_stats
            else:
                diff = 0
            
            for d in nst:
                k = '%s.%s' % (d['scope'], d['mname'])
                _type = d['type']
                scope = d['scope']
                if _type == 'gauge':
                    c_stats[k] = {'type':_type, 'key':k, 'value':d['value'], 'scope':scope}
                elif _type == 'rate':
                    o = c_stats.get(k, {})
                    rate_f = d['rate_f']
                    if o == {}:
                        # If there is no old value, don't need to compare rate as
                        # there is no older value
                        c_stats[k] = {'type':_type, 'key':k, 'value':None, 'raw_value':d['value'], 'scope':scope}
                        continue
                    
                    if rate_f is None:
                        rate_v = (d['value'] - o['raw_value']) / diff
                    else:
                        rate_v = rate_f(o['raw_value'], d['value'], diff)
                    c_stats[k] = {'type':_type, 'key':k, 'value':rate_v, 'raw_value':d['value'], 'scope':scope}
                    
            self.stats[cid] = c_stats

        # Keep stats only for the known containers
        to_del = []
        for cid in self.stats:
            if cid not in self.containers:
                to_del.append(cid)
        for cid in to_del:
            if cid in self.containers:
                del self.containers[cid]
            
        # tag the current time so we can diff rate in the future
        self.last_stats = now

        # Now pack the value based on the images if need
        self.aggregate_stats()
        

    # pack stats based on the container id but also merge/sum values for the
    # same images
    def aggregate_stats(self):
        if self.con is None:
            return
        images = {}
        for (cid, cont) in self.containers.iteritems():
            # avoid containers with no stats, it's not a good thing here :)
            if cid not in self.stats:
                continue
            img = cont.get('image')
            if not img in images:
                images[img] = []
            images[img].append(cid)

        img_stats = {}
        #print "IMAGES", images
        for (img, cids) in images.iteritems():
            #print 'IMAGE', img
            #print cids
            s = {}
            img_stats[img] = s
            for cid in cids:
                for (k, d) in self.stats[cid].iteritems():
                    # if the first value, keep it as a whole
                    if s.get(k, None) is None:
                        s[k] = d
                        continue
                    c = s[k]
                    
                    if d['value'] is not None:
                        if c['value'] is None:
                            c['value'] = d['value']
                        else:
                            c['value'] += d['value']
        
        images_stats = {}
        # Now be sure to have updated images
        self.load_images()
        
        for (img_id, s) in img_stats.iteritems():
            img = None
            for d in self.images:
                if d['Id'] == img_id:
                    img = d
                    break
            # No more image?
            if img is None:
                continue
            imgname = img['RepoTags'][0]
            images_stats[imgname] = s
        self.images_stats = images_stats
        #print 'Finally compute', self.images_stats


    def do_stats_loop(self):
        while True:
            self.connect()
            if not self.con:
                time.sleep(1) # do not hammer the connexion
                continue
            # Each seconds we are computing several stats on the containers and images
            # thanks to cgroups
            self.compute_stats()
            time.sleep(10)
            
            
    def do_loop(self):
        self.connect()
        self.load_containers()
        self.load_images()        
        while True:
            self.connect()
            if not self.con:
                time.sleep(1) # do not hammer the connexion
                continue
            now = int(time.time())
            try:
                evts = get_json("/events", local_socket='/var/run/docker.sock', params={'until':now, 'since':now - 1}, multi=True)
            except Exception, exp:
                logger.debug('cannot get docker events: %s' % exp)
                time.sleep(1)
                continue
            logger.debug("GET docker events %s" % evts)
            # docker an return one or more dict
            if isinstance(evts, dict):
                evts = [evts]
            # now manage events and lock on it
            #evts = self.con.events() # can lock here
            for ev in evts:
                evdata = ev
                _id = evdata["id"]
                status = evdata["status"]
                if status in ("die", "stop"):
                    if _id in self.containers:
                        logger.debug('removing a container %s' % _id)
                        del self.containers[_id]
                        # stats will be cleaned on the next computation
                    else:
                        logger.debug('Asking to remove an unknow container? %s' % _id)
                elif status == 'start':
                    self.load_container(_id)
                else:
                    logger.debug('UNKNOWN EVENT IN DOCKER %s' % status)
            time.sleep(1)
                    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):

        @route('/docker/')
        @route('/docker')
        def get_docker():
            response.content_type = 'application/json'
            return json.dumps(self.con is not None)
    

        @route('/docker/containers')
        @route('/docker/containers/')
        def get_containers():
            response.content_type = 'application/json'
            return json.dumps(self.containers.values())

        
        @route('/docker/containers/:_id')
        def get_container(_id):
            response.content_type = 'application/json'
            cont = self.containers.get(_id, None)
            return json.dumps(cont)
    

        @route('/docker/images')
        @route('/docker/images/')
        def get_images():
            response.content_type = 'application/json'
            if self.con is None:
                return json.dumps(None)
            imgs = get_json('/images/json', local_socket='/var/run/docker.sock')
            r = [lower_dict(d) for d in imgs]
            return json.dumps(r)

        
        @route('/docker/images/:_id')
        def get_images(_id):
            response.content_type = 'application/json'
            if self.con is None:
                return json.dumps(None)
            imgs = get_json('/images/json', local_socket='/var/run/docker.sock')            
            for d in imgs:
                if d['Id'] == _id:
                    return json.dumps(lower_dict(d))
            return json.dumps(None)

        
        @route('/docker/stats')
        @route('/docker/stats/')
        def _stats():
            response.content_type = 'application/json'
            return self.get_stats()
        
        

dockermgr = DockerManager()
                    


    
