import time

from opsbro.collector import Collector


class Timezone(Collector):
    def launch(self):
        self.logger.debug('getTimezone: starting')
        res = {'timezone': time.tzname[1]}
        return res
