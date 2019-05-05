from .log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('server-identity')


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class ServerIdentity(object):
    def __init__(self):
        pass


serveridentity_ = None


def get_serveridentity():
    global serveridentity_
    if serveridentity_ is None:
        logger.debug('Lazy creation of the server identiry object')
        serveridentity_ = ServerIdentity()
        # NOTE: the detection of the driver will be done by the launcher
    return serveridentity_
