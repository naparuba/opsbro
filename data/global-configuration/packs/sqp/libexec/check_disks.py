import sys
import os
import imp

my_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, my_dir)

m = imp.load_source('synology_data', os.path.join(my_dir, 'synology_data.py'))

c = m.SynologyCheck()
results = c.get_disks_data()

warningTemperature = 50
criticalTemperature = 60

disks = results['disks']
raid_status = results['raid_status']
raid_name = results['raid_name']

whole_status = []

# Raid status
if raid_status == 'normal':
    s = (0, 'RAID status: OK', [])
else:
    s = (2, 'RAID status: the raid %s is %s' % (raid_name, raid_status), [])
whole_status.append(s)

for (disk_name, disk) in disks.iteritems():
    disk_status = disk['status']
    disk_temperature = disk['temperature']
    if disk_status == 'normal' and disk_temperature < warningTemperature:
        s = (0, 'Disk %s is OK. Temperature=%sC' % (disk_name, disk_temperature), {'disk_%s_temperature' % disk_name: disk_temperature})
    elif disk_status != 'normal' and disk_temperature < warningTemperature:
        s = (2, 'Disk %s is %s. Temperature=%sC' % (disk_name, disk_status, disk_temperature), {'disk_%s_temperature' % disk_name: disk_temperature})
    elif disk_temperature >= criticalTemperature:
        s = (2, 'Disk %s temperature is too high %sC' % (disk_name, disk_temperature), {'disk_%s_temperature' % disk_name: disk_temperature})
    elif disk_temperature >= warningTemperature:
        s = (1, 'Disk %s temperature is high %sC' % (disk_name, disk_temperature), {'disk_%s_temperature' % disk_name: disk_temperature})
    else:
        continue
    whole_status.append(s)

exit_status = max([s[0] for s in whole_status])
# print "Overall status:", exit_status
exit_text = {0: 'OK', 1: 'WARNING', 2: 'CRITICAL'}.get(exit_status)
status_txt = '\n'.join([' - %s' % s[1] for s in whole_status])
print 'Synology Disks are %s:\n%s' % (exit_text, status_txt)
