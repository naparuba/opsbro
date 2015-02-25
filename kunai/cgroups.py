#!/usr/bin/env python
import os
import time
import sys

from kunai.stats import STATS
from kunai.log import logger
from kunai.threadmgr import threader
from kunai.now import NOW
from kunai.httpdaemon import route, response


# linux only, because to problems for other os :)

# Basic USER_HZ, something like 100 (means 100 tick by seconds)
SC_CLK_TCK = os.sysconf_names['SC_CLK_TCK']
USER_HZ = os.sysconf(SC_CLK_TCK)


# For some cpu, we want the pct but the diff
# is an absolute value, in number of HZ
def rate_cpu(old_v, new_v, diff):
    
    return ((new_v - old_v) / float(diff)) / USER_HZ

CGROUP_METRICS = [
    {
        "cgroup": "memory",
        "file": "memory.stat",
        "cname": "memory",
        "metrics": {
            # Default metrics
            "cache": ("docker.mem.cache", "gauge", None),
            "rss": ("docker.mem.rss", "gauge", None),
            "swap": ("docker.mem.swap", "gauge", None),
            
            # Optional metrics
            "active_anon": ("docker.mem.active_anon", "gauge", None),
            "active_file": ("docker.mem.active_file", "gauge", None),
            "inactive_anon": ("docker.mem.inactive_anon", "gauge", None),
            "inactive_file": ("docker.mem.inactive_file", "gauge", None),
            "mapped_file": ("docker.mem.mapped_file", "gauge", None),
            "pgfault": ("docker.mem.pgfault", "rate", None),
            "pgmajfault": ("docker.mem.pgmajfault", "rate", None),
            "pgpgin": ("docker.mem.pgpgin", "rate", None),
            "pgpgout": ("docker.mem.pgpgout", "rate", None),
            "unevictable": ("docker.mem.unevictable", "gauge", None),
        }
    },
    {
        "cgroup": "cpuacct",
        "file": "cpuacct.stat",
        "cname": "cpu",
        "metrics": {
            "user": ("docker.cpu.user", "rate", rate_cpu),
            "system": ("docker.cpu.system", "rate", rate_cpu),
        },
    },
]



class CgroupMgr(object):
    def __init__(self):
        
        # Locate cgroups directories
        self._mountpoints = {}
        self._cgroup_filename_pattern = None
        for metric in CGROUP_METRICS:
            self._mountpoints[metric["cgroup"]] = self._find_cgroup(metric["cgroup"])
        

    # Cgroups
    def _find_cgroup_filename_pattern(self):
        if self._mountpoints:
            # We try with different cgroups so that it works even if only one is properly working
            for mountpoint in self._mountpoints.values():
                stat_file_path_lxc = os.path.join(mountpoint, "lxc")
                stat_file_path_docker = os.path.join(mountpoint, "docker")
                stat_file_path_coreos = os.path.join(mountpoint, "system.slice")

                if os.path.exists(stat_file_path_lxc):
                    return os.path.join('%(mountpoint)s/lxc/%(id)s/%(file)s')
                elif os.path.exists(stat_file_path_docker):
                    return os.path.join('%(mountpoint)s/docker/%(id)s/%(file)s')
                elif os.path.exists(stat_file_path_coreos):
                    return os.path.join('%(mountpoint)s/system.slice/docker-%(id)s.scope/%(file)s')

        raise Exception("Cannot find Docker cgroup directory. Be sure your system is supported.")

    
    def _get_cgroup_file(self, cgroup, container_id, filename):
        # This can't be initialized at startup because cgroups may not be mounted yet
        if not self._cgroup_filename_pattern:
            self._cgroup_filename_pattern = self._find_cgroup_filename_pattern()

        return self._cgroup_filename_pattern % (dict(
                    mountpoint=self._mountpoints[cgroup],
                    id=container_id,
                    file=filename,
                ))

    
    # There are old and new school format for cgroup. Manage both
    def _find_cgroup(self, hierarchy):
        with open("/proc/mounts") as fp:
            mounts = map(lambda x: x.split(), fp.read().splitlines())
        cgroup_mounts = filter(lambda x: x[2] == "cgroup", mounts)
        if len(cgroup_mounts) == 0:
            return ''
        # Old cgroup style
        if len(cgroup_mounts) == 1:
            return cgroup_mounts[0][1]
        # so new one
        for _, mountpoint, _, opts, _, _ in cgroup_mounts:
            if hierarchy in opts:
                return mountpoint
            

    # Parse a cgroup file and get a key/value return
    def _parse_cgroup_file(self, stat_file):
        try:
            logger.debug("Opening cgroup file: %s" % stat_file)
            with open(stat_file) as fp:
                return dict(map(lambda x: x.split(), fp.read().splitlines()))
        except IOError:
            # It is possible that the container got stopped between the API call and now
            logger.info("Can't open %s. Theses metrics for this container are skipped." % stat_file)
            return None
        
    
    def get_containers_metrics(self, containers):
        collect_uncommon_metrics = True
        tags = []
        res = {}
        for cid in containers:
            res[cid] = []
            for cgroup in CGROUP_METRICS:
                stat_file = self._get_cgroup_file(cgroup["cgroup"], cid, cgroup['file'])
                stats = self._parse_cgroup_file(stat_file)
                if stats:
                    for key, (dd_key, metric_type, rate_f) in cgroup['metrics'].iteritems():
                        if key in stats:# and (common_metric or collect_uncommon_metrics):
                            v = {'type': metric_type, 'scope':cgroup["cname"], 'mname':key, 'value':int(stats[key]), 'rate_f':rate_f}
                            res[cid].append(v)
        return res






cgroupmgr = CgroupMgr()
