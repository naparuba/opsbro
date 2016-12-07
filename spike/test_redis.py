import socket

addr = '127.0.0.1'
port = 6379

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((addr, port))
s.send('INFO\n')
data = s.recv(8096)
s.close()

print data