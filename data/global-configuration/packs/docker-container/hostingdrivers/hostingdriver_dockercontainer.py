import os

from opsbro.hostingdrivermanager import InterfaceHostingDriver


class DockerContainerHostingDriver(InterfaceHostingDriver):
    name = 'docker-container'
    
    
    def __init__(self):
        super(DockerContainerHostingDriver, self).__init__()
        self.__uuid = None
    
    
    def __get_uuid(self):
        pth = '/proc/self/cgroup'
        with open(pth, 'r') as f:
            buf = f.readlines()[0].strip()
            # Example: 10:perf_event:/docker/349be0ab91c71c4596bbdef670df3574ac20f2620dbb96743c9035d619625f36
            self.__uuid = buf.split('/')[-1]
    
    
    # Docker container have all the /.dockerenv file
    def is_active(self):
        return os.path.exists('/.dockerenv')
