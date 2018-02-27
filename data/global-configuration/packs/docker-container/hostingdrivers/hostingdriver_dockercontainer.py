import os

from opsbro.hostingdrivermanager import InterfaceHostingDriver, HOSTING_DRIVER_LAYER_CONTAINER


class DockerContainerHostingDriver(InterfaceHostingDriver):
    name = 'docker-container'
    layer = HOSTING_DRIVER_LAYER_CONTAINER
    
    
    def __init__(self):
        super(DockerContainerHostingDriver, self).__init__()
        self.__uuid = None
    
    
    # Docker container have all the /.dockerenv file
    def is_active(self):
        return os.path.exists('/.dockerenv')
    
    
    def get_unique_uuid(self):
        pth = '/proc/self/cgroup'
        with open(pth, 'r') as f:
            buf = f.readlines()[0].strip()
            # Example: 10:perf_event:/docker/349be0ab91c71c4596bbdef670df3574ac20f2620dbb96743c9035d619625f36
            self.__uuid = buf.split('/')[-1]
        self.logger.info('Using docker container uuid as unique uuid for this node.')
        return self.__uuid
