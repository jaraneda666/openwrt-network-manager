from openwrt_client import OpenWrtClient

client = OpenWrtClient(host="192.168.1.1")
try:
    client.connect()
    commands = [
        ("IPSEC_CHECK", "which ipsec charon 2>/dev/null; ps | grep -E 'ipsec|charon' | grep -v grep"),
        ("WIREGUARD_PKG", "opkg list-installed | grep -E 'wireguard|kmod-wireguard|luci-app-wireguard'"),
        ("SAMBA_RUNNING", "/etc/init.d/samba4 status 2>/dev/null"),
        ("UPNP_CONFIG", "uci show upnpd"),
        ("DNSMASQ_BIND", "uci show dhcp | grep -E 'localservice|nonwildcard|interface|notfound'"),
        ("SYSCTL_SECURITY", "sysctl net.ipv4.conf.all.accept_redirects net.ipv4.conf.all.send_redirects net.ipv4.conf.all.accept_source_route net.ipv4.tcp_syncookies"),
    ]
    for title, cmd in commands:
        code, out, err = client.exec_command(cmd, check_safety=False)
        print(f"=== {title} ===")
        print(out.strip())
        print()
finally:
    client.close()
