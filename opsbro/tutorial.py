import os

from .log import LoggerFactory
from .jsonmgr import jsoner

# Global logger for this part
logger = LoggerFactory.create_logger('monitoring')


class Tutorial(object):
    def __init__(self, name, title, dir_name, tutorial_data_pth, pack_level, pack_name):
        self.name = name
        self.title = title
        self.dir_name = dir_name
        self.pack_level = pack_level
        self.pack_name = pack_name
        self.tutorial_data_path = tutorial_data_pth
    
    
    def get_tutorial_data(self):
        with open(self.tutorial_data_path, 'r') as f:
            buf = f.read()
            
            data = jsoner.loads(buf, encoding='utf8')
            return data
    
    
    def get_duration(self):
        data = self.get_tutorial_data()
        return data['duration']


class Tutorials(object):
    def __init__(self):
        self.tutorials = []
    
    
    # Load and sanatize a check object in our configuration
    def import_tutorial(self, tutorial_cfg, fr, pack_name='', pack_level=''):
        title = tutorial_cfg.get('title', 'no tutorial title')
        dir_name = os.path.dirname(fr)
        tutorial_data_pth = os.path.join(dir_name, 'tutorial-data.json')
        if not os.path.exists(tutorial_data_pth):
            err = 'The tutorial at %s is missing the tutorial-data.json file in the same directory.' % dir_name
            logger.error(err)
            raise Exception(err)
        
        # Tutorial name is the name of the directory
        tutorial_name = os.path.split(dir_name)[-1]
        tutorial = Tutorial(tutorial_name, title, dir_name, tutorial_data_pth, pack_level, pack_name)
        self.tutorials.append(tutorial)


tutorialmgr = Tutorials()
