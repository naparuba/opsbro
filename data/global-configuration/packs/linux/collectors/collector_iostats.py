import sys
import re
import traceback
from kunai.log import logger
from kunai.collector import Collector


class IoStats(Collector):
    def launch(self):
        # logger.debug('getIOStats: start')

        iostats = {}

        if sys.platform != 'linux2':
            logger.debug('getIOStats: unsupported platform')
            return False

        # logger.debug('getIOStats: linux2')

        headerRegexp = re.compile(r'([%\\/\-\_a-zA-Z0-9]+)[\s+]?')
        itemRegexp = re.compile(r'^([a-zA-Z0-9\/]+)')
        valueRegexp = re.compile(r'\d+\.\d+')

        try:
            _cmd = 'iostat -d 1 2 -x -k'
            stats = self.execute_shell(_cmd)
            if not stats:
                logger.error('getIOStats: exception in launching command')
                return False

            recentStats = stats.split('Device:')[2].split('\n')
            header = recentStats[0]
            headerNames = re.findall(headerRegexp, header)
            device = None

            for statsIndex in range(1, len(recentStats)):
                row = recentStats[statsIndex]

                if not row:
                    # Ignore blank lines.
                    continue

                deviceMatch = re.match(itemRegexp, row)

                if deviceMatch is not None:
                    # Sometimes device names span two lines.
                    device = deviceMatch.groups()[0]

                values = re.findall(valueRegexp, row.replace(',', '.'))

                if not values:
                    # Sometimes values are on the next line so we encounter
                    # instances of [].
                    continue

                iostats[device] = {}

                for headerIndex in range(0, len(headerNames)):
                    headerName = headerNames[headerIndex]
                    iostats[device][headerName] = float(values[headerIndex])

        except Exception:
            logger.error('getIOStats: exception = %s', traceback.format_exc())
            return False

        # logger.debug('getIOStats: completed, returning')
        return iostats
