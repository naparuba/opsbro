from opsbro.collector import Collector


class Co2(Collector):
    def __init__(self):
        super(Co2, self).__init__()
        self.lib = None
    
    
    def launch(self):
        
        if not self.is_in_group('co2'):
            self.set_not_eligible('Please add the "co2" group to enable this collector.')
            return
        
        if self.lib is None:
            try:
                import mh_z19
                self.lib = mh_z19
            except ImportError:
                self.set_error('You need the python mh-z19 librairy to collect for Co2.')
                return False
        
        try:
            data = self.lib.read_all()
        except Exception as exp:
            err = 'Cannot call mh_z19 captor, look if is is connected: %s' % exp
            self.set_error(err)
            return False
        
        r = {'co2': data['co2'], 'temperature': data['temperature']}
        self.logger.debug('CO2/MHZ19 raw value: %s   return %s' % (data, r))
        return r
