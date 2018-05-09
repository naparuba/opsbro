import socket

msg = \
    'M-SEARCH * HTTP/1.1\r\n' \
    'HOST:239.255.255.250:1900\r\n' \
    'ST:upnp:rootdevice\r\n' \
    'MX:2\r\n' \
    'MAN:"ssdp:discover"\r\n'


msg = \
    'M-SEARCH * HTTP/1.1\r\n' \
    'HOST:239.255.255.250:1900\r\n' \
    'ST:urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n' \
    'Man:"ssdp:discover"\r\n' \
    'MX:3\r\n'

msg = """M-SEARCH * HTTP/1.1
Host:239.255.255.250:1900
ST:urn:schemas-upnp-org:device:InternetGatewayDevice:1
Man:"ssdp:discover"
MX:3
"""
# Set up UDP socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.settimeout(10)
s.sendto(msg, ('239.255.255.250', 1900) )

try:
    while True:
        data, addr = s.recvfrom(65507)
        print addr, data
except socket.timeout:
    print "TIMEOUT"
print "exit"