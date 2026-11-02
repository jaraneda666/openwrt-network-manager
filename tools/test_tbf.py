import paramiko, pathlib

k = str(pathlib.Path.home() / '.ssh' / 'id_ed25519')
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.1.253', username='root', key_filename=k)
_, out, err = s.exec_command("tc qdisc add dev phy0-ap0 root tbf rate 5mbit burst 32k latency 50ms && tc qdisc show dev phy0-ap0 && tc qdisc del dev phy0-ap0 root && tc qdisc show dev phy0-ap0")
print("STDOUT:", out.read().decode())
print("STDERR:", err.read().decode())
s.close()
