import subprocess

def run_ssh(host, cmd):
    res = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', f'root@{host}', cmd], capture_output=True, text=True)
    return res.stdout

print("=== LEASES ===")
print(run_ssh('192.168.1.1', 'cat /tmp/dhcp.leases'))

print("=== STATIC HOSTS IN UCI ===")
print(run_ssh('192.168.1.1', "uci show dhcp | grep -E 'host\\[[0-9]+\\]\\.(name|ip|mac)'"))

print("=== AP1 ASSOCIATIONS ===")
print(run_ssh('192.168.1.253', 'iwinfo phy0-ap0 assoclist; echo "---AP1-2.4G---"; iwinfo phy1-ap1 assoclist; echo "---AP1-IOT---"; iwinfo phy1-ap2 assoclist'))

print("=== AP2 ASSOCIATIONS ===")
print(run_ssh('192.168.1.254', 'iwinfo phy0-ap0 assoclist; echo "---AP2-2.4G---"; iwinfo phy1-ap1 assoclist; echo "---AP2-IOT---"; iwinfo phy1-ap2 assoclist'))
