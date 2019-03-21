import os
import json
from bottle import route, run, request, static_file
import tarfile
import tempfile


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


my_dir = os.path.dirname(os.path.abspath(__file__))


@route('/version', method='GET')
def get_version():
    version_file = os.path.join(my_dir, 'monitoring_pack', 'version')
    with open(version_file, 'r') as f:
        version = f.read().strip()
    return version


tmp_file_fd, tmp_file_pth = tempfile.mkstemp()
os.close(tmp_file_fd)


@route('/monitoring_pack.tar.gz')
def get_monitoring_pack():
    global tmp_file_pth
    # TODO: manage a lock for this or better do in memory and cache it
    print "CREATING TAR GZ ON", tmp_file_pth
    make_tarfile(tmp_file_pth, os.path.join(my_dir, 'monitoring_pack'))
    return static_file(os.path.basename(tmp_file_pth), root=os.path.dirname(tmp_file_pth))


@route('/sqp', method='POST')
def get_from_synology():
    data = json.loads(request.body.getvalue())
    
    # print "Here are results", data, type(data)
    customer_key = data['customer_key']
    
    # TODO: LOOKUP CUSTOMER KE FOR VALID ENTRY in the SaaS
    
    # get basic info
    node_uuid = data['uuid']
    inventory_number = data['inventory_number']
    results = data['results']
    
    warningTemperature = 50
    criticalTemperature = 60
    
    dsm_version = results['dsm_version']
    disks = results['disks']
    temperature = results['temperature']
    system_status = results['system_status']
    cpu_fan_status = results['cpu_fan_status']
    raid_status = results['raid_status']
    power_status = results['power_status']
    raid_name = results['raid_name']
    system_fan_status = results["system_fan_status"]
    dsm_upgrade_available = results['dsm_upgrade_available']
    serial = results['serial']
    model = results['model']
    
    whole_status = []
    
    # System status
    if system_status == 'normal':
        s = (0, 'System status: OK', [])
    else:
        s = (2, 'System status: %s' % system_status, [])
    whole_status.append(s)
    
    # CPU FAN
    if cpu_fan_status == 'normal':
        s = (0, 'CPU FAN status: OK', [])
    else:
        s = (2, 'CPU FAN status: %s' % cpu_fan_status, [])
    whole_status.append(s)
    
    # System FAN
    if system_fan_status == 'normal':
        s = (0, 'System FAN status: OK', [])
    else:
        s = (2, 'system FAN status: %s' % system_fan_status, [])
    whole_status.append(s)
    
    # Power status
    if power_status == 'normal':
        s = (0, 'Power status: OK', [])
    else:
        s = (2, 'Power status: %s' % power_status, [])
    whole_status.append(s)
    
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
    
    # Temperature
    if temperature >= criticalTemperature:
        s = (2, 'Temperature: CRITICAL - %sC is too high (>%sC)' % (temperature, criticalTemperature), {'temperature': temperature})
    elif temperature >= warningTemperature:
        s = (1, 'Temperature: WARNING - %sC is high (>%sC)' % (temperature, warningTemperature), {'temperature': temperature})
    else:
        s = (0, 'Temperature: OK - %sC is valid' % (temperature), {'temperature': temperature})
    whole_status.append(s)
    
    whole_status.append((0, 'DSM upgrade: %s' % dsm_upgrade_available, {}))
    
    exit_status = max([s[0] for s in whole_status])
    # print "Overall status:", exit_status
    exit_text = {0: 'OK', 1: 'WARNING', 2: 'CRITICAL'}.get(exit_status)
    status_txt = '\n'.join([' - %s' % s[1] for s in whole_status])
    print 'Synology device (serial=%s) (model=%s) (version=%s) is %s:\n%s' % (serial, model, dsm_version, exit_text, status_txt)
    
    # TODO: export status to shinken via a receiver


run(host='0.0.0.0', port=8080)
