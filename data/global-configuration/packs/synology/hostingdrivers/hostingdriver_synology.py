import os

from opsbro.hostingdrivermanager import InterfaceHostingDriver, HOSTING_DRIVER_LAYER_PHYSICAL


class DockerContainerHostingDriver(InterfaceHostingDriver):
    name = 'synology'
    layer = HOSTING_DRIVER_LAYER_PHYSICAL
    
    
    def __init__(self):
        super(DockerContainerHostingDriver, self).__init__()
        self.__meta_data = None
    
    
    # Synology linux have the /etc/synoinfo.conf with various parameters
    def is_active(self):
        return os.path.exists('/etc/synoinfo.conf')
    
    
    # we will get some meta data in the /proc/cmdline file that have:
    # root=/dev/md0 earlyprintk=apl console=ttyS2,115200n8 ihd_num=2 netif_num=2 HddHotplug=1 SataPortMap=21 syno_hw_version=DS718+ vender_format_version=2 syno_hdd_detect=18,179,176,175 syno_hdd_enable=21,20,19,9 syno_usb_vbus_gpio=13@0000:00:15.0@3 sn=18A0PEN558404 macs=0011329f0943,0011329f0944
    # number_of_disks => ihd_num=2
    # number_of_iface => netif_num=2
    # are_disks_hotplug =>  HddHotplug=1
    # model => syno_hw_version=DS718+
    # serial => sn=18A0PEN558404
    def get_meta_data(self):
        if self.__meta_data is not None:
            return self.__meta_data
        
        self.__meta_data = {}
        if not os.path.exists('/proc/cmdline'):  # not a synology linux?
            raise Exception('Seems that this system is not a synology linux, cannot find /proc/cmdline')
        
        with open('/proc/cmdline', 'r') as f:
            buf = f.read().strip()
        
        elts = buf.split(' ')
        for elt in elts:
            if '=' not in elt:
                continue
            key, value = elt.split('=', 1)
            if key == 'syno_hw_version':
                self.__meta_data['model'] = value
                continue
            if key == 'sn':
                self.__meta_data['serial'] = value
                continue
            if key == 'HddHotplug':  # this one int oa bool
                self.__meta_data['are_disks_hotplug'] = (value == '1')
                continue
            if key == 'netif_num':  # into int
                self.__meta_data['number_of_iface'] = int(value)
                continue
            if key == 'ihd_num':  # into int
                self.__meta_data['number_of_disks'] = int(value)
                continue
        return self.__meta_data
    
    
    # The synology bios is fake, so use the board serial number
    def get_unique_uuid(self):
        try:
            meta_data = self.get_meta_data()
        except Exception as exp:
            self.logger.error('Cannot get unique uuid for your EC2 instance. Error: %s' % exp)
            raise
        serial = meta_data['serial']
        self.logger.info('Using Synology model serial number (%s) as unique uuid for this node.' % serial)
        return serial
