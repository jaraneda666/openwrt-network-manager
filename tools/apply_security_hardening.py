import sys
import time
from openwrt_client import OpenWrtClient

client = OpenWrtClient(host="192.168.1.1")
try:
    client.connect()
    print("=== PASO 1: DETENER Y DESHABILITAR SAMBA 4 ===")
    code, out, err = client.exec_command("/etc/init.d/samba4 stop && /etc/init.d/samba4 disable", check_safety=False)
    print(f"Samba status: code {code}, out: {out.strip()}, err: {err.strip()}")

    print("\n=== PASO 2: FIJAR DROPBEAR (SSH) ESTRICTAMENTE A INTERFAZ LAN ===")
    # Dropbear: Interface='lan'
    dropbear_cmds = (
        "uci set dropbear.main.Interface='lan' && "
        "uci commit dropbear && "
        "/etc/init.d/dropbear restart"
    )
    code, out, err = client.exec_command(dropbear_cmds, check_safety=False)
    print(f"Dropbear config: code {code}")
    
    # Verificar conexion SSH inmediatamente
    time.sleep(1)
    code, out, err = client.exec_command("echo 'SSH reconectado con exito'")
    print(f"Verificacion SSH: {out.strip()}")

    print("\n=== PASO 3: HARDENING DE KERNEL (SYSCTL: ANTI-SPOOFING Y REDIRECTS) ===")
    sysctl_content = (
        "# Hardening de red OpenWrt\n"
        "net.ipv4.conf.all.rp_filter = 1\n"
        "net.ipv4.conf.default.rp_filter = 1\n"
        "net.ipv4.conf.all.send_redirects = 0\n"
        "net.ipv4.conf.default.send_redirects = 0\n"
        "net.ipv4.conf.all.accept_redirects = 0\n"
        "net.ipv4.conf.default.accept_redirects = 0\n"
    )
    cmd_sysctl = f"cat << 'EOF' > /etc/sysctl.d/99-security.conf\n{sysctl_content}EOF\nsysctl -p /etc/sysctl.d/99-security.conf"
    code, out, err = client.exec_command(cmd_sysctl, check_safety=False)
    print(f"Sysctl aplicado:\n{out.strip()}")

    print("\n=== PASO 4: DEPURACION DE REGLAS ZOMBIE EN FIREWALL ===")
    # Identificar y eliminar reglas inactivas y zombies:
    # 1. Allow-IPSec-ESP
    # 2. Allow-ISAKMP
    # 3. Allow_443 (la regla erronea con src_port=443, no el redirect)
    # 4. wg (Allow-WireGuard)
    # 5. Allow_Wireguard (redirect)
    # 6. ovpn (Allow-OpenVPN)
    # 7. Allow-OpenVPN-Inbound
    uci_firewall_cleanup = """
# Buscar indices o nombres de secciones
for sec in $(uci show firewall | grep -E "name='Allow-IPSec-ESP'|name='Allow-ISAKMP'|name='Allow_443'|name='Allow-WireGuard'|name='Allow_Wireguard'|name='Allow-OpenVPN'|name='Allow-OpenVPN-Inbound'" | cut -d'.' -f1,2); do
    echo "Eliminando regla zombie: $sec"
    uci delete "$sec"
done
uci commit firewall
/etc/init.d/firewall reload
"""
    code, out, err = client.exec_command(uci_firewall_cleanup, check_safety=False)
    print(f"Firewall cleanup:\n{out.strip()}")

    print("\n=== PASO 5: VERIFICACION FINAL ===")
    # 1. Puertos en escucha relevantes
    code, out, err = client.exec_command("netstat -tulnp | grep -E 'dropbear|smbd|nmbd'")
    print("Servicios dropbear/samba activos:")
    print(out.strip() or "Ningun servicio smbd/nmbd detectado.")

    # 2. Sysctl en vivo
    code, out, err = client.exec_command("sysctl net.ipv4.conf.all.rp_filter net.ipv4.conf.all.send_redirects net.ipv4.conf.all.accept_redirects")
    print("\nValores sysctl actuales:")
    print(out.strip())

    # 3. Reglas WAN input actuales en nftables
    code, out, err = client.exec_command("nft list chain inet fw4 input_wan 2>/dev/null")
    print("\nCadena input_wan nftables:")
    print(out.strip())

    # 4. Port forwards actuales (dstnat)
    code, out, err = client.exec_command("uci show firewall | grep -E 'redirect\\[.*\\.name'")
    print("\nRedirecciones port forwarding activas:")
    print(out.strip())

except Exception as e:
    print(f"Error durante aplicacion: {e}")
finally:
    client.close()
