import httplib
import urllib2
import traceback
from kunai.log import logger
from kunai.collector import Collector


class Apache(Collector):
    def launch(self):
        logger.debug('getApacheStatus: start')

        if 'apacheStatusUrl' in self.config and self.config[
            'apacheStatusUrl'] != 'http://www.example.com/server-status/?auto':  # Don't do it if the status URL hasn't been provided
            logger.debug('getApacheStatus: config set')

            try:
                logger.debug('getApacheStatus: attempting urlopen')

                if 'apacheStatusUser' in self.config and 'apacheStatusPass' in self.config and self.config[
                    'apacheStatusUrl'] != '' and self.config['apacheStatusPass'] != '':
                    logger.debug('getApacheStatus: u/p config set')
                    passwordMgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
                    passwordMgr.add_password(None, self.config['apacheStatusUrl'], self.config['apacheStatusUser'],
                                             self.config['apacheStatusPass'])

                    handler = urllib2.HTTPBasicAuthHandler(passwordMgr)

                    # create "opener" (OpenerDirector instance)
                    opener = urllib2.build_opener(handler)

                    # use the opener to fetch a URL
                    opener.open(self.config['apacheStatusUrl'])

                    # Install the opener.
                    # Now all calls to urllib2.urlopen use our opener.
                    urllib2.install_opener(opener)

                req = urllib2.Request(self.config['apacheStatusUrl'], None, {})
                request = urllib2.urlopen(req)
                response = request.read()

            except urllib2.HTTPError, e:
                logger.error('Unable to get Apache status - HTTPError = %s', e)
                return False
            except urllib2.URLError, e:
                logger.error('Unable to get Apache status - URLError = %s', e)
                return False
            except httplib.HTTPException, e:
                logger.error('Unable to get Apache status - HTTPException = %s', e)
                return False
            except Exception:
                logger.error('Unable to get Apache status - Exception = %s', traceback.format_exc())
                return False

            logger.debug('getApacheStatus: urlopen success, start parsing')

            # Split out each line
            lines = response.split('\n')

            # Loop over each line and get the values
            apacheStatus = {}

            logger.debug('getApacheStatus: parsing, loop')

            # Loop through and extract the numerical values
            for line in lines:
                values = line.split(': ')

                try:
                    apacheStatus[str(values[0])] = values[1]

                except IndexError:
                    break

            logger.debug('getApacheStatus: parsed')

            apacheStatusReturn = {}

            try:
                if apacheStatus['Total Accesses'] != False:
                    logger.debug('getApacheStatus: processing total accesses')
                    totalAccesses = float(apacheStatus['Total Accesses'])

                    if self.apacheTotalAccesses is None or self.apacheTotalAccesses <= 0 or totalAccesses <= 0:
                        apacheStatusReturn['reqPerSec'] = 0.0
                        self.apacheTotalAccesses = totalAccesses
                        logger.debug(
                            'getApacheStatus: no cached total accesses (or totalAccesses == 0), so storing for first time / resetting stored value')
                    else:
                        logger.debug('getApacheStatus: cached data exists, so calculating per sec metrics')
                        apacheStatusReturn['reqPerSec'] = (totalAccesses - self.apacheTotalAccesses) / 60
                        self.apacheTotalAccesses = totalAccesses
                else:
                    logger.error(
                        'getApacheStatus: Total Accesses not present in mod_status output. Is ExtendedStatus enabled?')
            except IndexError:
                logger.error(
                    'getApacheStatus: IndexError - Total Accesses not present in mod_status output. Is ExtendedStatus enabled?')
            except KeyError:
                logger.error(
                    'getApacheStatus: KeyError - Total Accesses not present in mod_status output. Is ExtendedStatus enabled?')

            try:
                if apacheStatus['BusyWorkers'] != False and apacheStatus['IdleWorkers'] != False:
                    apacheStatusReturn['busyWorkers'] = apacheStatus['BusyWorkers']
                    apacheStatusReturn['idleWorkers'] = apacheStatus['IdleWorkers']
                else:
                    logger.error(
                        'getApacheStatus: BusyWorkers/IdleWorkers not present in mod_status output. Is the URL correct (must have ?auto at the end)?')
            except IndexError:
                logger.error(
                    'getApacheStatus: IndexError - BusyWorkers/IdleWorkers not present in mod_status output. Is the URL correct (must have ?auto at the end)?')
            except KeyError:
                logger.error(
                    'getApacheStatus: KeyError - BusyWorkers/IdleWorkers not present in mod_status output. Is the URL correct (must have ?auto at the end)?')

            if 'reqPerSec' in apacheStatusReturn or 'BusyWorkers' in apacheStatusReturn or 'IdleWorkers' in apacheStatusReturn:
                return apacheStatusReturn
            else:
                return False

        else:
            logger.debug('getApacheStatus: config not set')

            return False
