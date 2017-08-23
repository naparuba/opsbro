import socket

from opsbro.misc.IPy import IP
from opsbro.evaluater import export_evaluater_function


@export_evaluater_function
def ip_is_in_range(ip, range):
    """**ip_is_in_range(ip, range)** -> return True if the ip is in the ip range, False otherwise.

 * ip:     (string) ip (v4 or v6) to check
 * range:  (string) ip range that the ip must be in


<code>
    Example:
        ip_is_in_range('172.16.0.30', '172.16.0.0/24')
    Returns:
        True
</code>
    """
    
    ip_range = IP(range)
    return ip in ip_range


@export_evaluater_function
def check_tcp(host, port, timeout=10):
    """**check_tcp(host, port, timeout=10)** -> return True if the TCP connection can be established, False otherwise.

 * host: (string) ip/fqdn of the host to connect to.
 * port: (integer) TCP port to connect to
 * timeout [optionnal] (integer) timeout to use for the connection test.

<code>
 Example:
     check_tcp('www.google.com', 80)

 Returns:
     True
</code>

    """
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except socket.error:
        sock.close()
        return False


@export_evaluater_function
def ip_to_host(ip):
    """**ip_to_host(ip)** -> return the hostname if the ip is founded in the DNS server, '' otherwise.

 * ip: (string) ip of the host to get hostname from reverse DNS.

<code>
 Example:
     ip_to_host('172.217.23.35')

 Returns:
     'lhr35s02-in-f35.1e100.net'
</code>

    """
    try:
        hname, tmp = socket.gethostbyaddr(ip)
        # clean the last . if there is one
        if hname.endswith('.'):
            return hname[:-1]
    except socket.error:
        return ''


@export_evaluater_function
def host_to_ip(hname):
    """**host_to_ip(hname)** -> return the ip if founded, '' otherwise.

 * hname: (string) name of the host to get IP from DNS.

<code>
 Example:
     host_to_ip('www.google.com')

 Returns:
     '74.125.206.147'
</code>

    """
    try:
        ip = socket.gethostbyname(hname)
        return ip
    except socket.error:
        return ''
