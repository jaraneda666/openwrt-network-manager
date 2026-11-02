from openwrt_client import OpenWrtClient

client = OpenWrtClient(host="192.168.1.1")
try:
    client.connect()
    code, out, _ = client.exec_command("cat /var/etc/miniupnpd.conf 2>/dev/null || cat /etc/miniupnpd.conf 2>/dev/null")
    print("=== CURRENT MINIUPNPD.CONF ===")
    print(out)
finally:
    client.close()
