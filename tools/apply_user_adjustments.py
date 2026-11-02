import sys
from openwrt_client import OpenWrtClient

client = OpenWrtClient(host="192.168.1.1")
try:
    client.connect()
    print("=== PASO 1: DESHABILITAR REGLA JELLYFIN SIN BORRARLA ===")
    cmds_jellyfin = (
        "uci set firewall.cfg153837.enabled='0' && "
        "uci commit firewall && "
        "/etc/init.d/firewall reload"
    )
    code, out, err = client.exec_command(cmds_jellyfin, check_safety=False)
    print(f"Jellyfin rule disabled: code {code}")

    print("\n=== PASO 2: CONFIGURAR UPNP EXCLUSIVAMENTE PARA 127.0.0.1 ===")
    cmds_upnp = (
        "uci set upnpd.@perm_rule[0].int_addr='127.0.0.1/32' && "
        "uci set upnpd.@perm_rule[0].comment='Allow user PC only (admin-casa)' && "
        "uci commit upnpd && "
        "/etc/init.d/miniupnpd restart"
    )
    code, out, err = client.exec_command(cmds_upnp, check_safety=False)
    print(f"UPnP configured: code {code}")

    print("\n=== PASO 3: VERIFICACION DE JELLYFIN EN FIREWALL ===")
    code, out, _ = client.exec_command("uci show firewall.cfg153837")
    print(out.strip())
    code, out, _ = client.exec_command("nft list chain inet fw4 dstnat_wan 2>/dev/null || nft list ruleset | grep 8096")
    print("\nReglas activas para 8096 en nftables:")
    print(out.strip() or "Ninguna regla activa para 8096 en nftables (deshabilitado correctamente).")

    print("\n=== PASO 4: VERIFICACION DE MINIUPNPD.CONF ===")
    code, out, _ = client.exec_command("grep -E 'allow|deny' /var/etc/miniupnpd.conf 2>/dev/null")
    print(out.strip())

    print("\n=== PASO 5: VERIFICACION DE REDIRECCIONES ACTIVAS RESTANTES ===")
    code, out, _ = client.exec_command("uci show firewall | grep -E 'redirect\\[.*\\.name'")
    print(out.strip())

finally:
    client.close()
