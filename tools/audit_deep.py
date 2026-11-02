from openwrt_client import OpenWrtClient

client = OpenWrtClient(host="192.168.1.1")
try:
    client.connect()
    checks = [
        ("UPNP_LEASES", "cat /var/run/miniupnpd.leases 2>/dev/null || echo 'No leases'"),
        ("WIREGUARD_STATUS", "wg show 2>/dev/null || uci show network | grep -i wireguard"),
        ("OPENVPN_PROCESS", "ps | grep -i openvpn | grep -v grep"),
        ("SAMBA_SHARES", "uci show samba4"),
        ("DISKS_MOUNTS", "df -h && block info 2>/dev/null"),
        ("BANIP_STATUS", "/etc/init.d/banip status 2>/dev/null || ubus call banip status 2>/dev/null"),
        ("NFT_WAN_INPUT", "nft list chain inet fw4 input_wan 2>/dev/null || iptables -L zone_wan_input -v -n 2>/dev/null"),
        ("NFT_PORT_FORWARDS", "nft list chain inet fw4 dstnat 2>/dev/null"),
        ("IP_FORWARDING", "sysctl net.ipv4.ip_forward net.ipv4.conf.all.rp_filter net.ipv4.conf.default.rp_filter"),
        ("PASSWORDS_SUDO", "cat /etc/passwd"),
    ]
    for title, cmd in checks:
        code, out, err = client.exec_command(cmd, check_safety=False)
        print(f"=== {title} ===")
        print(out.strip())
        print()
finally:
    client.close()
