import os
from opsbro.collector import Collector

if os.name == 'nt':
    import opsbro.misc.wmi as wmi


class IIS(Collector):
    def launch(self):
        # logger.debug('getMemoryUsage: start')
        if os.name != 'nt':
            self.set_not_eligible('This collector is only available on Windows')
            return False
        
        if not self.is_in_group('iis-server'):
            self.set_not_eligible('Please add the iis-server group to enable this collector.')
        
        data = {}
        counters = [
            (r'iis total bytes/sec', r'\web service(_total)\bytes total/sec', 100),
            (r'iis current connections', r'\web service(_total)\current connections', 0),
            (r'asp.net total requests failed', r'\asp.net applications(__total__)\requests failed', 0),
            (r'asp.net total requests/sec', r'\asp.net applications(__total__)\requests/sec', 100),
            (r'asp.net total errors/sec', r'\asp.net applications(__total__)\errors total/sec', 100),
            (r'asp.net total pipeline instance count', r'\asp.net applications(__total__)\pipeline instance count', 0),
            (r'asp.net total sessions active', r'\asp.net applications(__total__)\sessions active', 0),
            (r'asp.net requests queued', r'\asp.net\requests queued', 0),
        ]
        for c in counters:
            _label = c[0]
            _query = c[1]
            _delay = c[2]
            try:
                v = wmi.wmiaccess.get_perf_data(_query, unit='double', delay=_delay)
            except WindowsError:  # no such info
                continue
            data[_label] = v
        
        return data
