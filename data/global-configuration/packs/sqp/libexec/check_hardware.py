import sys
import os
import imp

my_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, my_dir)

m = imp.load_source('synology_data', os.path.join(my_dir, 'synology_data.py'))

c = m.SynologyCheck()
results = c.get_hardware_data()

warningTemperature = 50
criticalTemperature = 60

temperature = results['temperature']
system_status = results['system_status']
cpu_fan_status = results['cpu_fan_status']
power_status = results['power_status']
system_fan_status = results["system_fan_status"]

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

# Temperature
if temperature >= criticalTemperature:
    s = (2, 'Temperature: CRITICAL - %sC is too high (>%sC)' % (temperature, criticalTemperature), {'temperature': temperature})
elif temperature >= warningTemperature:
    s = (1, 'Temperature: WARNING - %sC is high (>%sC)' % (temperature, warningTemperature), {'temperature': temperature})
else:
    s = (0, 'Temperature: OK - %sC is valid' % (temperature), {'temperature': temperature})
whole_status.append(s)

exit_status = max([s[0] for s in whole_status])
# print "Overall status:", exit_status
exit_text = {0: 'OK', 1: 'WARNING', 2: 'CRITICAL'}.get(exit_status)
status_txt = '\n'.join([' - %s' % s[1] for s in whole_status])
print 'Synology system is %s:\n%s' % (exit_text, status_txt)
