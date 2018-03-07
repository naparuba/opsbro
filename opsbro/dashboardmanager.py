from .log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('dashboard')


class DashboardManager(object):
    def __init__(self):
        self.dashboards = {}
    
    
    def import_dashboard(self, o, fname, gname, mod_time=0, pack_name='', pack_level=''):
        o['pack_name'] = pack_name
        o['pack_level'] = pack_level
        self.dashboards[gname.split('/')[-1]] = o


dashboarder = None


def get_dashboarder():
    global dashboarder
    if dashboarder is None:
        logger.debug('Lazy creation of the dashboarder class')
        dashboarder = DashboardManager()
    return dashboarder
