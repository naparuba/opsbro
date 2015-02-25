#!/usr/bin/python

# -*- coding: utf-8 -*-


#==> need to rewrite or at least have a common lib with shinken or nagios

import re


perfdata_split_pattern = re.compile('([^=]+=\S+)')
metric_pattern = re.compile('^([^=]+)=([\d\.\-\+eE]+)([\w\/%]*);?([\d\.\-\+eE:~@]+)?;?([\d\.\-\+eE:~@]+)?;?([\d\.\-\+eE]+)?;?([\d\.\-\+eE]+)?;?\s*')


def to_best_int_float(val):
    i = int(float(val))
    f = float(val)
    # If the f is a .0 value,
    # best match is int
    if i == f:
        return i
    return f


# If we can return an int or a float, or None
# if we can't
def guess_int_or_float(val):
    try:
        return to_best_int_float(val)
    except Exception, exp:
        return None


# Class for one metric of a perf_data
class Metric:
    def __init__(self, s):
        self.name = self.value = self.uom = self.warning = self.critical = self.min = self.max = None
        s = s.strip()
        r = metric_pattern.match(s)
        if r:
            # Get the name but remove all ' in it
            self.name = r.group(1).replace("'", "")
            self.value = guess_int_or_float(r.group(2))
            self.uom = r.group(3)
            self.warning = guess_int_or_float(r.group(4))
            self.critical = guess_int_or_float(r.group(5))
            self.min = guess_int_or_float(r.group(6))
            self.max = guess_int_or_float(r.group(7))
            if self.uom == '%':
                self.min = 0
                self.max = 100

    def __str__(self):
        s = "%s=%s%s" % (self.name, self.value, self.uom)
        if self.warning:
            s = s + ";%s" % (self.warning)
        if self.critical:
            s = s + ";%s" % (self.critical)
        return s


class PerfDatas:
    def __init__(self, s):
        s = s or ''
        elts = perfdata_split_pattern.findall(s)
        elts = [e for e in elts if e != '']
        self.metrics = {}
        for e in elts:
            m = Metric(e)
            if m.name is not None:
                self.metrics[m.name] = m

    def __iter__(self):
        return self.metrics.itervalues()

    def __len__(self):
        return len(self.metrics)

    def __getitem__(self, key):
        return self.metrics[key]

    def __contains__(self, key):
        return key in self.metrics

