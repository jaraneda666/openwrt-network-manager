import paramiko

target = "192.168.1.100"
user = os.environ.get("ADMIN_USER", "admin")
pwd = os.environ.get("ADMIN_PASS", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(target, 22, user, pwd, timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f"echo {pwd} | sudo -S {cmd}")
    return stdout.read().decode('utf-8', errors='replace').strip()

print("=== OTP CHECK ===")
print(run("find /usr/syno/etc/preference/ -type f 2>/dev/null; ls -la /usr/syno/etc/preference/admin/ 2>/dev/null"))
print(run("synogetkeyvalue /etc/synoinfo.conf enable_otp; synogetkeyvalue /etc/synoinfo.conf otp_enforce_option"))

print("\n=== AUTOBLOCK CONFIG ===")
print(run("cat /etc/synoautoblock.conf 2>/dev/null || cat /usr/syno/etc/synoautoblock.conf 2>/dev/null || grep -i autoblock /etc/synoinfo.conf"))

client.close()
