import time
from kunai.log import logger
from kunai.collector import Collector


class Timezone(Collector):
    def launch(self):
        logger.debug('getTimezone: starting')
        res = {'timezone': time.tzname[1]}
        return res
