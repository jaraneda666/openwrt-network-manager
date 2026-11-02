import datetime
from pathlib import Path
import paramiko

key_file = str(Path.home() / ".ssh" / "id_ed25519")
host = "192.168.1.1"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, port=22, username="root", key_filename=key_file, timeout=10)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code

# 1. Backup
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = Path("output") / "backups" / f"google_home_migration_{ts}"
backup_dir.mkdir(parents=True, exist_ok=True)

out_dhcp, _, _ = run("cat /etc/config/dhcp")
out_fw, _, _ = run("cat /etc/config/firewall")

with open(backup_dir / "dhcp.uci", "w", encoding="utf-8") as f:
    f.write(out_dhcp)
with open(backup_dir / "firewall.uci", "w", encoding="utf-8") as f:
    f.write(out_fw)

print(f"[+] Respaldos guardados en {backup_dir}")

# 2. Modify DHCP
# Check host index for google-home
out_idx, _, _ = run("uci show dhcp | grep -i '6C:5A:B5:58:03:68'")
print(f"[+] Entrada actual en DHCP: {out_idx}")

# Update host and domain
cmd_dhcp = """
uci set dhcp.@host[2].ip='192.168.50.7'
uci set dhcp.@domain[18].ip='192.168.50.7'
uci commit dhcp
/etc/init.d/dnsmasq reload
"""
out, err, code = run(cmd_dhcp)
print(f"[+] Actualizado DHCP: {code}")

# 3. Modify Firewall
# a) Add to whitelist if not already present
# b) Add rule to drop traffic from 192.168.50.7 to 192.168.1.0/24 (LAN)
# c) Add rule to drop traffic from 192.168.50.7 to router management (22, 80, 443)
cmd_fw = """
# Whitelist for WAN access
uci -q del_list firewall.drop_unknown_mac.src_mac='!6c:5a:b5:58:03:68'
uci -q del_list firewall.drop_unknown_mac.src_mac='!6C:5A:B5:58:03:68'
uci add_list firewall.drop_unknown_mac.src_mac='!6c:5a:b5:58:03:68'

# Isolate from rest of LAN
uci -q delete firewall.isolate_google_home_lan
uci set firewall.isolate_google_home_lan=rule
uci set firewall.isolate_google_home_lan.name='Isolate-Google-Home-from-LAN'
uci set firewall.isolate_google_home_lan.src='lan'
uci set firewall.isolate_google_home_lan.dest='lan'
uci set firewall.isolate_google_home_lan.src_ip='192.168.50.7'
uci set firewall.isolate_google_home_lan.dest_ip='192.168.1.0/24'
uci set firewall.isolate_google_home_lan.target='DROP'

# Isolate from router management ports (LuCI / SSH)
uci -q delete firewall.block_google_home_admin
uci set firewall.block_google_home_admin=rule
uci set firewall.block_google_home_admin.name='Block-Google-Home-Router-Admin'
uci set firewall.block_google_home_admin.src='lan'
uci set firewall.block_google_home_admin.src_ip='192.168.50.7'
uci set firewall.block_google_home_admin.dest_port='22 80 443'
uci set firewall.block_google_home_admin.proto='tcp'
uci set firewall.block_google_home_admin.target='REJECT'

if fw4 check; then
    uci commit firewall
    /sbin/fw4 reload
    echo "FW4_RELOAD_SUCCESS"
else
    uci revert firewall
    echo "FW4_CHECK_FAILED"
fi
"""

out, err, code = run(cmd_fw)
print(f"[+] Firewall output:\n{out}\n{err}")

ssh.close()
