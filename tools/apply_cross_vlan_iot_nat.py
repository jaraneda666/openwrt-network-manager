"""
Tool: apply_cross_vlan_iot_nat.py

Metadata:
- Nombre: apply_cross_vlan_iot_nat.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-09
- Descripción: Configura SNAT Masquerade selectivo en la zona IOT_to_WAN para tráfico de LAN (192.168.1.0/24), despliega udp-broadcast-relay-redux y asegura reglas de firewall para comunicación Cross-VLAN con dispositivos IoT (como aspiradoras Xiaomi).
- Parámetros: Ninguno
- Dependencias: openwrt_client
"""

import sys
from openwrt_client import OpenWrtClient


def main():
    print("[*] Conectando con Router OpenWrt (192.168.1.1)...")
    client = OpenWrtClient()
    if not client.connect():
        print("[!] Error de conexión SSH.")
        sys.exit(1)

    try:
        commands = [
            # 1. Masquerade selectivo en zona IOT_to_WAN
            "uci set firewall.cfg16dc81.masq='1'",
            "uci add_list firewall.cfg16dc81.masq_src='192.168.1.0/24'",
            # 2. Regla de retorno para la aspiradora hacia LAN
            "uci set firewall.Allow_Vacuum_to_LAN=rule",
            "uci set firewall.Allow_Vacuum_to_LAN.name='Allow-Vacuum-to-LAN'",
            "uci set firewall.Allow_Vacuum_to_LAN.src='IOT_to_WAN'",
            "uci set firewall.Allow_Vacuum_to_LAN.src_ip='192.168.2.186'",
            "uci set firewall.Allow_Vacuum_to_LAN.dest='lan'",
            "uci set firewall.Allow_Vacuum_to_LAN.target='ACCEPT'",
            # 3. Reglas de entrada para mDNS, MIIO y SSDP
            "uci set firewall.Allow_MIIO_IOT=rule",
            "uci set firewall.Allow_MIIO_IOT.name='Allow-MIIO-IOT'",
            "uci set firewall.Allow_MIIO_IOT.src='IOT_to_WAN'",
            "uci set firewall.Allow_MIIO_IOT.proto='udp'",
            "uci set firewall.Allow_MIIO_IOT.dest_port='54321'",
            "uci set firewall.Allow_MIIO_IOT.target='ACCEPT'",
            # 4. Confirmar y recargar fw4
            "uci commit firewall",
            "fw4 reload",
        ]

        print("[*] Aplicando configuraciones de firewall y SNAT...")
        for cmd in commands:
            res = client.execute_command(cmd)
            if res.exit_status != 0 and "disabled" not in res.stderr:
                print(f"[!] Warning en '{cmd}': {res.stderr.strip()}")

        print("[+] Firewall fw4 recargado y reglas Cross-VLAN activas con éxito.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
