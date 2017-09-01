import time
import socket
import hashlib
import json
import re
import cPickle
import base64
import requests as rq

# DO NOT FORGEET:
# sysctl -w net.core.rmem_max=26214400


from opsbro.threadmgr import threader
from opsbro.module import ListenerModule
from opsbro.stop import stopper
from opsbro.ts import tsmgr
from opsbro.stats import STATS
from opsbro.httpdaemon import http_export, response, request, abort
from opsbro.util import to_best_int_float
from opsbro.gossip import gossiper
from opsbro.httpclient import HTTP_EXCEPTIONS
from opsbro.kv import kvmgr
from opsbro.parameters import BoolParameter, IntParameter


class GraphiteModule(ListenerModule):
    implement = 'graphite'
    
    parameters = {
        'enabled': BoolParameter(default=False),
        'port'   : IntParameter(default=2003),
        'udp'    : BoolParameter(default=True),
        'tcp'    : BoolParameter(default=True),
    }
    
    
    def __init__(self):
        ListenerModule.__init__(self)
        
        # Graphite reaping queue
        self.graphite_queue = []
        
        self.enabled = False
        self.graphite_port = 2003
        self.addr = '0.0.0.0'

        self.graphite_tcp_sock = None
        self.graphite_udp_sock = None
    
    
    # Prepare to open the UDP port
    def prepare(self):
        self.logger.debug('Graphite: prepare phase')
        
        self.enabled = self.get_parameter('enabled')
        self.graphite_port = self.get_parameter('port')
        
        if self.enabled:
            
            ########### TCP
            self.graphite_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.graphite_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.graphite_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
            self.graphite_tcp_sock.bind((self.addr, self.graphite_port))
            self.graphite_tcp_sock.listen(5)
            self.logger.info("TS Graphite TCP port open", self.graphite_port)
            
            ############ UDP
            self.graphite_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
            self.graphite_udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.graphite_udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
            self.logger.log(self.graphite_udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
            self.graphite_udp_sock.bind((self.addr, self.graphite_port))
            self.logger.info("TS Graphite UDP port open", self.graphite_port)
            self.logger.debug("UDP RCVBUF", self.graphite_udp_sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
        
        else:
            self.logger.info('Graphite is not enabled, skipping it')
    
    
    def get_info(self):
        return {'graphite_configuration': self.get_config(), 'graphite_info': None}
    
    
    def launch(self):
        threader.create_and_launch(self.launch_graphite_udp_listener, name='UDP port:%d listening' % self.graphite_port, essential=True, part='graphite')
        threader.create_and_launch(self.launch_graphite_tcp_listener, name='TCP port:%d listening' % self.graphite_port, essential=True, part='graphite')
        threader.create_and_launch(self.graphite_reaper, name='Metric reader', essential=True, part='graphite')
    
    
    # Thread for listening to the graphite port in UDP (2003)
    def launch_graphite_udp_listener(self):
        while not stopper.interrupted:
            if not self.enabled:
                time.sleep(1)
                continue
            try:
                data, addr = self.graphite_udp_sock.recvfrom(65535)
            except socket.timeout:  # loop until we got some data
                continue
            self.logger.debug("UDP Graphite: received message:", len(data), addr)
            STATS.incr('ts.graphite.udp.receive', 1)
            self.graphite_queue.append(data)
    
    
    # Same but for the TCP connections
    # TODO: use a real daemon part for this, this is not ok for fast receive
    def launch_graphite_tcp_listener(self):
        while not stopper.interrupted:
            if not self.enabled:
                time.sleep(1)
                continue
            try:
                conn, addr = self.graphite_tcp_sock.accept()
            except socket.timeout:  # loop until we got some connect
                continue
            conn.settimeout(5.0)
            self.logger.debug('TCP Graphite Connection address:', addr)
            data = ''
            while True:
                try:
                    ldata = conn.recv(1024)
                except Exception, exp:
                    break
                if not ldata:
                    break
                # Look at only full lines, and not the last part
                # So we look at the position of the last \n
                lst_nidx = ldata.rfind('\n')
                # take all finished lines
                data += ldata[:lst_nidx + 1]
                STATS.incr('ts.graphite.tcp.receive', 1)
                self.graphite_queue.append(data)
                # stack the data with the garbage so we will continue it
                # on the next turn
                data = ldata[lst_nidx + 1:]
            conn.close()
            # Also stack what the last send
            self.graphite_queue.append(data)
    
    
    # Main graphite reaper thread, that will get data from both tcp and udp flow
    # and dispatch it to the others daemons if need
    def graphite_reaper(self):
        while not stopper.interrupted:
            graphite_queue = self.graphite_queue
            self.graphite_queue = []
            if len(graphite_queue) > 0:
                self.logger.info("Graphite queue", len(graphite_queue))
            for data in graphite_queue:
                T0 = time.time()
                self.grok_graphite_data(data)
                STATS.timer('ts.graphite.grok-graphite-data', (time.time() - T0) * 1000)
            time.sleep(0.1)
    
    
    # Lookup at the graphite lines compat,  run in the graphite-reaper thread
    def grok_graphite_data(self, data):
        STATS.incr('ts.graphite.grok.data', 1)
        forwards = {}
        for line in data.splitlines():
            elts = line.split(' ')
            elts = [s.strip() for s in elts if s.strip()]
            
            if len(elts) != 3:
                return
            mname, value, timestamp = elts[0], elts[1], elts[2]
            hkey = hashlib.sha1(mname).hexdigest()
            ts_node_manager = gossiper.find_group_node('ts', hkey)
            # if it's me that manage this key, I add it in my backend
            if ts_node_manager == gossiper.uuid:
                self.logger.debug("I am the TS node manager")
                try:
                    timestamp = int(timestamp)
                except ValueError:
                    return
                value = to_best_int_float(value)
                if value is None:
                    continue
                tsmgr.tsb.add_value(timestamp, mname, value)
            # not me? stack a forwarder
            else:
                self.logger.debug("The node manager for this Ts is ", ts_node_manager)
                l = forwards.get(ts_node_manager, [])
                l.append(line)
                forwards[ts_node_manager] = l
        
        for (uuid, lst) in forwards.iteritems():
            node = gossiper.get(uuid)
            # maybe the node disapear? bail out, we are not lucky
            if node is None:
                continue
            packets = []
            # first compute the packets
            buf = ''
            for line in lst:
                buf += line + '\n'
                if len(buf) > 1024:
                    packets.append(buf)
                    buf = ''
            if buf != '':
                packets.append(buf)
            
            # UDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for packet in packets:
                # do NOT use the node['port'], it's the internal communication, not the graphite one!
                sock.sendto(packet, (node['addr'], self.graphite_port))
            sock.close()
            
            '''
            # TCP mode
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect( (node['addr'], self.graphite_port) )
            for packet in packets:
               sock.sendall(packet)
            sock.close()
            '''
    
    
    # Export end points to get/list TimeSeries
    def export_http(self):
        
        @http_export('/metrics/find/')
        def get_graphite_metrics_find():
            response.content_type = 'application/json'
            key = request.GET.get('query', '*')
            print "LIST GET TS FOR KEY", key
            
            recursive = False
            if key.endswith('.*'):
                recursive = True
                key = key[:-2]
                print "LIST RECURSVIE FOR", key
            
            # Maybe ask all, if so recursive is On
            if key == '*':
                key = ''
                recursive = True
            
            r = []
            keys = tsmgr.list_keys(key)
            l = len(key)
            added = {}
            for k in keys:
                print "LIST KEY", k
                title = k[l:]
                # maybe we got a key that do not belong to us
                # like srv-linux10 when we ask for linux1
                # so if we don't got a . here, it's an invalid
                # dir
                print "LIST TITLE", title
                if key and not title.startswith('.'):
                    print "LIST SKIPPING KEY", key
                    continue
                
                # Ok here got sons, but maybe we are not asking for recursive ones, if so exit with
                # just the key as valid tree
                if not recursive:
                    print "NO RECURSIVE AND EARLY EXIT for KEY", key
                    return json.dumps(
                        [{"leaf": 0, "context": {}, 'text': key, 'id': key, "expandable": 1, "allowChildren": 1}])
                
                if title.startswith('.'):
                    title = title[1:]
                print "LIST TITLE CLEAN", title
                # if there is a . in it, it's a dir we need to have
                dname = title.split('.', 1)[0]
                # If the dnmae was not added, do it
                if dname not in added and title.count('.') != 0:
                    added[dname] = True
                    r.append({"leaf"         : 0, "context": {}, 'text': dname, 'id': k[:l] + dname, 'expandable': 1,
                              'allowChildren': 1})
                    print "LIST ADD DIR", dname, k[:l] + dname
                
                print "LIST DNAME KEY", dname, key, title.count('.')
                if title.count('.') == 0:
                    # not a directory, add it directly but only if the
                    # key asked was our directory
                    r.append({"leaf": 1, "context": {}, 'text': title, 'id': k, "expandable": 0, "allowChildren": 0})
                    print "LIST ADD FILE", title
            print "LIST FINALLY RETURN", r
            return json.dumps(r)
        
        
        # really manage the render call, with real return, call by a get and
        # a post function
        def do_render(targets, _from):
            response.content_type = 'application/json'
            
            if not targets:
                return abort(400, 'Invalid target')
            # Default past values, round at an hour
            now = int(time.time())
            pastraw = int(time.time()) - 86400
            past = divmod(pastraw, 3600)[0] * 3600
            
            found = False
            m = re.match(r'-(\d*)h', _from, re.M | re.I)
            if m:
                found = True
                nbhours = int(m.group(1))
                pastraw = int(time.time()) - (nbhours * 3600)
                past = divmod(pastraw, 3600)[0] * 3600
            if not found:
                m = re.match(r'-(\d*)hours', _from, re.M | re.I)
                if m:
                    found = True
                    nbhours = int(m.group(1))
                    pastraw = int(time.time()) - (nbhours * 3600)
                    past = divmod(pastraw, 3600)[0] * 3600
            if not found:  # absolute value maybe?
                m = re.match(r'(\d*)', _from, re.M | re.I)
                if m:
                    found = True
                    past = divmod(int(m.group(1)), 3600)[0] * 3600
            
            if not found:
                return abort(400, 'Invalid range')
            
            # Ok now got the good values
            res = []
            for target in targets:
                
                nuuid = gossiper.find_group_node('ts', target)
                n = None
                if nuuid:
                    n = gossiper.get(nuuid)
                nname = ''
                if n:
                    nname = n['name']
                self.logger.debug('HTTP ts: target %s is managed by %s(%s)' % (target, nname, nuuid))
                # that's me or the other is no more there?
                if nuuid == self.uuid or n is None:
                    self.logger.debug('HTTP ts: /render, my job to manage %s' % target)
                    
                    # Maybe I am also the TS manager of these data? if so, get the TS backend data for this
                    min_e = hour_e = day_e = None
                    
                    self.logger.debug('HTTP RENDER founded TS %s' % tsmgr.tsb.data)
                    min_e = tsmgr.tsb.data.get('min::%s' % target, None)
                    hour_e = tsmgr.tsb.data.get('hour::%s' % target, None)
                    day_e = tsmgr.tsb.data.get('day::%s' % target, None)
                    self.logger.debug('HTTP TS RENDER, FOUNDED TS data %s %s %s' % (min_e, hour_e, day_e))
                    
                    # Get from the past, but start at the good hours offset
                    t = past
                    r = []
                    
                    while t < now:
                        # Maybe the time match a hour we got in memory, if so take there
                        if hour_e and hour_e['hour'] == t:
                            self.logger.debug('HTTP TS RENDER match memory HOUR, take this value instead')
                            raw_values = hour_e['values'][:]  # copy instead of cherrypick, because it can move/append
                            for i in xrange(60):
                                # Get teh value and the time
                                e = raw_values[i]
                                tt = t + 60 * i
                                r.append((e, tt))
                                if e:
                                    self.logger.debug('GOT NOT NULL VALUE from RENDER MEMORY cache %s:%s' % (e, tt))
                        else:  # no memory match, got look in the KS part
                            ukey = '%s::h%d' % (target, t)
                            raw64 = kvmgr.get_key(ukey)
                            if raw64 is None:
                                for i in xrange(60):
                                    # Get the value and the time
                                    tt = t + 60 * i
                                    r.append((None, tt))
                            else:
                                raw = base64.b64decode(raw64)
                                v = cPickle.loads(raw)
                                raw_values = v['values']
                                for i in xrange(60):
                                    # Get teh value and the time
                                    e = raw_values[i]
                                    tt = t + 60 * i
                                    r.append((e, tt))
                        # Ok now the new hour :)
                        t += 3600
                    # Now build the final thing
                    res.append({"target": target, "datapoints": r})
                else:  # someone else job, rely the question
                    uri = 'http://%s:%s/render/?target=%s&from=%s' % (n['addr'], n['port'], target, _from)
                    try:
                        self.logger.debug('TS: (get /render) relaying to %s: %s' % (n['name'], uri))
                        r = rq.get(uri)
                        self.logger.debug('TS: get /render founded (%d)' % len(r.text))
                        v = json.loads(r.text)
                        self.logger.debug("TS /render relay GOT RETURN", v, "AND RES", res)
                        res.extend(v)
                        self.logger.debug("TS /render res is now", res)
                    except HTTP_EXCEPTIONS, exp:
                        self.logger.debug('TS: /render relay error asking to %s: %s' % (n['name'], str(exp)))
                        continue
            
            self.logger.debug('TS RENDER FINALLY RETURN', res)
            return json.dumps(res)
        
        
        @http_export('/render')
        @http_export('/render/')
        def get_ts_values():
            targets = request.GET.getall('target')
            _from = request.GET.get('from', '-24hours')
            return do_render(targets, _from)
        
        
        @http_export('/render', method='POST')
        @http_export('/render/', method='POST')
        def get_ts_values():
            targets = request.POST.getall('target')
            _from = request.POST.get('from', '-24hours')
            return do_render(targets, _from)
