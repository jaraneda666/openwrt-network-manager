import sys
from openwrt_client import OpenWrtClient

client = OpenWrtClient(host="192.168.1.1")
try:
    client.connect()
    sections = [
        ("LISTENING_PORTS", "netstat -tulnp 2>/dev/null || ss -tulnp 2>/dev/null"),
        ("DROPBEAR", "uci show dropbear"),
        ("UHTTPD", "uci show uhttpd"),
        ("UPNPD", "uci show upnpd 2>/dev/null"),
        ("SAMBA4", "uci show samba4 2>/dev/null"),
        ("OPENVPN", "uci show openvpn 2>/dev/null"),
        ("BANIP", "uci show banip 2>/dev/null"),
        ("FIREWALL_ZONES", "uci show firewall | grep -E 'zone|forwarding'"),
        ("FIREWALL_REDIRECTS", "uci show firewall | grep -E 'redirect'"),
        ("FIREWALL_INPUT_RULES", "uci show firewall | grep -E 'rule' | grep -E 'src=\x27wan\x27|src=\x27\*\x27'"),
    ]
    for title, cmd in sections:
        code, out, err = client.exec_command(cmd, check_safety=False)
        print(f"=== {title} ===")
        print(out.strip())
        print()
finally:
    client.close()
