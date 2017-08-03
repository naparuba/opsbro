import os
from opsbro.collector import Collector


# deferred : Stuck mails (that will be retried later)
# active : Mails being delivered (should be small)
# maildrop : Localy posted mail
# incoming : Processed local mail and received from network
# corrupt : Messages found to not be in correct format (shold be 0)
# hold : Recent addition, messages put on hold indefinitly - delete of free

class Postfix(Collector):
    types = ['deferred', 'active', 'maildrop', 'incoming', 'corrupt', 'hold']
    
    
    def __init__(self, config, put_result=None):
        super(Postfix, self).__init__(config, put_result)
        self.data = {}
        self.postfix_dir = '/var/spool/postfix'
    
    
    def count_sub_dir(self, sdir):
        counter = 0
        full_path = os.path.join(self.postfix_dir, sdir)
        for top, dirs, files in os.walk(full_path):
            counter += len(files)
        return counter
    
    
    def launch(self):
        if not os.path.exists(self.postfix_dir):
            return False
        for t in self.types:
            c = self.count_sub_dir(t)
            self.data['queue.' + t] = c
        return self.data
