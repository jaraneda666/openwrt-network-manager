"""
# Tool: apply_guest_iot_config.py

## Metadata
- Nombre: apply_guest_iot_config.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-06
- Descripción: Configura aislamiento, puertos restringidos y control de ancho de banda para red de Invitados (VLAN 70), resolución DNS/DHCP para IoT (VLAN 60) en el router OpenWrt y Wi-Fi abierto sin clave en APs.
- Parámetros: --router, --ap1, --ap2
- Dependencias: paramiko
"""

import argparse
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError:
    paramiko = None


def get_ssh(host, user="root", key_file=None):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=22, username=user, key_filename=key_file, timeout=10, look_for_keys=True, allow_agent=True)
    return client


def main():
    parser = argparse.ArgumentParser(description="Despliegue de red IoT e Invitados")
    parser.add_argument("--router", default="192.168.1.1", help="IP del Router OpenWrt")
    parser.add_argument("--ap1", default="192.168.1.253", help="IP del AP UniFi 253")
    parser.add_argument("--ap2", default="192.168.1.254", help="IP del AP UniFi 254")

    args = parser.parse_args()

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_str = str(default_ed25519) if default_ed25519.exists() else None

    # ==========================================
    # 1. ROUTER OPENWRT: DNS, FIREWALL & SQM
    # ==========================================
    print(f"1. Configurando Router OpenWrt ({args.router})...")
    r_ssh = get_ssh(args.router, key_file=key_str)

    # A) Ampliar bind_hosts en adguardhome.yaml
    print(" - Actualizando bind_hosts de AdGuardHome para VLAN 60 y 70...")
    cmd_adguard = """
python3 -c "
p = '/etc/adguardhome.yaml'
with open(p, 'r') as f:
    c = f.read()
if '192.168.2.1' not in c:
    c = c.replace('  bind_hosts:\\n    - 192.168.1.1\\n    - 127.0.0.1', '  bind_hosts:\\n    - 192.168.1.1\\n    - 192.168.2.1\\n    - 192.168.3.1\\n    - 127.0.0.1')
    with open(p, 'w') as f:
        f.write(c)
" 2>/dev/null || sed -i '/- 127.0.0.1/a \    - 192.168.2.1\\n    - 192.168.3.1' /etc/adguardhome.yaml
/etc/init.d/adguardhome restart
"""
    r_ssh.exec_command(cmd_adguard)

    # B) Reglas de Firewall para DHCP y DNS en IoT e Invitados
    print(" - Configurando reglas de Firewall UCI (DHCP, DNS y puertos web para Invitados)...")
    fw_cmds = """
# Reglas de acceso a servicios del router para IOT
uci -q delete firewall.Allow_DHCP_IOT
uci set firewall.Allow_DHCP_IOT=rule
uci set firewall.Allow_DHCP_IOT.name='Allow-DHCP-IOT'
uci set firewall.Allow_DHCP_IOT.src='IOT_to_WAN'
uci set firewall.Allow_DHCP_IOT.proto='udp'
uci set firewall.Allow_DHCP_IOT.dest_port='67'
uci set firewall.Allow_DHCP_IOT.target='ACCEPT'

uci -q delete firewall.Allow_DNS_IOT
uci set firewall.Allow_DNS_IOT=rule
uci set firewall.Allow_DNS_IOT.name='Allow-DNS-IOT'
uci set firewall.Allow_DNS_IOT.src='IOT_to_WAN'
uci set firewall.Allow_DNS_IOT.proto='tcp udp'
uci set firewall.Allow_DNS_IOT.dest_port='53'
uci set firewall.Allow_DNS_IOT.target='ACCEPT'

# Reglas de acceso a servicios del router para GUEST
uci -q delete firewall.Allow_DHCP_GUEST
uci set firewall.Allow_DHCP_GUEST=rule
uci set firewall.Allow_DHCP_GUEST.name='Allow-DHCP-GUEST'
uci set firewall.Allow_DHCP_GUEST.src='GUEST_to_WAN'
uci set firewall.Allow_DHCP_GUEST.proto='udp'
uci set firewall.Allow_DHCP_GUEST.dest_port='67'
uci set firewall.Allow_DHCP_GUEST.target='ACCEPT'

uci -q delete firewall.Allow_DNS_GUEST
uci set firewall.Allow_DNS_GUEST=rule
uci set firewall.Allow_DNS_GUEST.name='Allow-DNS-GUEST'
uci set firewall.Allow_DNS_GUEST.src='GUEST_to_WAN'
uci set firewall.Allow_DNS_GUEST.proto='tcp udp'
uci set firewall.Allow_DNS_GUEST.dest_port='53'
uci set firewall.Allow_DNS_GUEST.target='ACCEPT'

# Restringir salida de Invitados hacia WAN: Solo HTTP (80), HTTPS (443) e ICMP
# Primero removemos el reenvío genérico total si existiera
for f in $(uci show firewall | grep -E "src='GUEST_to_WAN'.*dest='wan'" | cut -d'.' -f2 | cut -d'=' -f1); do
    uci -q delete firewall.$f
done

# Regla de reenvío controlado para Invitados: HTTP (80)
uci -q delete firewall.Guest_Allow_HTTP
uci set firewall.Guest_Allow_HTTP=rule
uci set firewall.Guest_Allow_HTTP.name='Guest-Allow-HTTP'
uci set firewall.Guest_Allow_HTTP.src='GUEST_to_WAN'
uci set firewall.Guest_Allow_HTTP.dest='wan'
uci set firewall.Guest_Allow_HTTP.proto='tcp'
uci set firewall.Guest_Allow_HTTP.dest_port='80'
uci set firewall.Guest_Allow_HTTP.target='ACCEPT'

# Regla de reenvío controlado para Invitados: HTTPS (443)
uci -q delete firewall.Guest_Allow_HTTPS
uci set firewall.Guest_Allow_HTTPS=rule
uci set firewall.Guest_Allow_HTTPS.name='Guest-Allow-HTTPS'
uci set firewall.Guest_Allow_HTTPS.src='GUEST_to_WAN'
uci set firewall.Guest_Allow_HTTPS.dest='wan'
uci set firewall.Guest_Allow_HTTPS.proto='tcp'
uci set firewall.Guest_Allow_HTTPS.dest_port='443'
uci set firewall.Guest_Allow_HTTPS.target='ACCEPT'

# Regla de reenvío controlado para Invitados: ICMP Ping
uci -q delete firewall.Guest_Allow_ICMP
uci set firewall.Guest_Allow_ICMP=rule
uci set firewall.Guest_Allow_ICMP.name='Guest-Allow-ICMP'
uci set firewall.Guest_Allow_ICMP.src='GUEST_to_WAN'
uci set firewall.Guest_Allow_ICMP.dest='wan'
uci set firewall.Guest_Allow_ICMP.proto='icmp'
uci set firewall.Guest_Allow_ICMP.target='ACCEPT'

uci commit firewall
/etc/init.d/firewall reload
"""
    stdin, stdout, stderr = r_ssh.exec_command(fw_cmds)
    stdout.channel.recv_exit_status()

    # C) Configurar SQM en br-lan.70 (10 Mbps Bajada / 2 Mbps Subida)
    print(" - Configurando SQM CAKE en interfaz br-lan.70 (10 Mbps Down / 2 Mbps Up)...")
    sqm_cmds = """
uci -q delete sqm.guest
uci set sqm.guest=queue
uci set sqm.guest.enabled='1'
uci set sqm.guest.interface='br-lan.70'
uci set sqm.guest.download='10000'
uci set sqm.guest.upload='2000'
uci set sqm.guest.qdisc='cake'
uci set sqm.guest.script='piece_of_cake.qos'
uci set sqm.guest.linklayer='none'
uci commit sqm
/etc/init.d/sqm restart
"""
    stdin, stdout, stderr = r_ssh.exec_command(sqm_cmds)
    stdout.channel.recv_exit_status()
    r_ssh.close()
    print("Router configurado con éxito.")

    # ==========================================
    # 2. ACCESS POINTS: WI-FI INVITADOS ABIERTO
    # ==========================================
    for ap in [args.ap1, args.ap2]:
        print(f"2. Configurando Wi-Fi Invitados en AP ({ap})...")
        ap_ssh = get_ssh(ap, key_file=key_str)
        ap_cmds = """
# Configurar Casa_Invitados 2.4 GHz sin contraseña y con aislamiento
uci set wireless.ap_guest2.encryption='none'
uci -q delete wireless.ap_guest2.key
uci set wireless.ap_guest2.isolate='1'

# Configurar Casa_Invitados 5 GHz sin contraseña y con aislamiento
uci set wireless.ap_guest5.encryption='none'
uci -q delete wireless.ap_guest5.key
uci set wireless.ap_guest5.isolate='1'

uci commit wireless
wifi reload
"""
        stdin, stdout, stderr = ap_ssh.exec_command(ap_cmds)
        stdout.channel.recv_exit_status()
        ap_ssh.close()
        print(f"AP {ap} configurado con éxito.")

    print("\n[DESPLIEGUE FINALIZADO CORRECTAMENTE]")


if __name__ == "__main__":
    main()
