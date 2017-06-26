import socket

from kunai.misc.IPy import IP
from kunai.evaluater import export_evaluater_function


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
