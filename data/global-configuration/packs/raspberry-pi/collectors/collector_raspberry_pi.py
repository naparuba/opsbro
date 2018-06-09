import os
from opsbro.collector import Collector


# deferred : Stuck mails (that will be retried later)
# active : Mails being delivered (should be small)
# maildrop : Localy posted mail
# incoming : Processed local mail and received from network
# corrupt : Messages found to not be in correct format (shold be 0)
# hold : Recent addition, messages put on hold indefinitly - delete of free

class RaspberryPi(Collector):
    
    def __init__(self):
        super(RaspberryPi, self).__init__()
        self.result = None
        self.version = None
    
    
    def _set_not_rpi(self):
        self.result = False
        self.set_not_eligible('This not not a respberry pi')
        return
    
    
    def _set_pi(self, version, temperature):
        self.version = version
        self.result = {'is_raspberry_pi': True, 'version': self.version, 'temperature': temperature}
    
    
    def launch(self):
        # Analyse only once
        if self.result is not None:
            return self.result
        
        if not os.path.exists('/sys/firmware/devicetree/base/model'):
            self._set_not_rpi()
            return False
        
        with open('/sys/firmware/devicetree/base/model', 'r') as f:
            buf = f.read().strip()
        # Possible:
        # Raspberry Pi Model B Plus Rev 1.2
        # Raspberry Pi 2 Model B Rev 1.1
        # Raspberry Pi Zero Rev 1.3
        # Raspberry Pi 3 Model B Rev 1.2
        if not buf.startswith('Raspberry Pi'):
            self._set_not_rpi()
            return False
        
        # Grok the temperature:
        temperature = 0
        if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = f.read().strip()
                temperature = int(int(temp) / 1000.0)
                
        
        if buf.startswith('Raspberry Pi Model'):
            self._set_pi('1', temperature)
            return self.result
        
        if buf.startswith('Raspberry Pi 2 Model'):
            self._set_pi('2', temperature)
            return self.result
        
        if buf.startswith('Raspberry Pi Zero'):
            self._set_pi('0', temperature)
            return self.result
        
        if buf.startswith('Raspberry Pi 3'):
            self._set_pi('3', temperature)
            return self.result
        
        self._set_pi('unknown', temperature)
        return self.result
