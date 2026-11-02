import paramiko, pathlib

k = str(pathlib.Path.home() / '.ssh' / 'id_ed25519')
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.1.253', username='root', key_filename=k)
_, out, _ = s.exec_command("opkg install tc-tiny kmod-sched-core")
print("=== INSTALL OUTPUT ===")
print(out.read().decode())
_, out, _ = s.exec_command("tc qdisc show")
print("=== TC QDISC SHOW ===")
print(out.read().decode())
s.close()
