"""
# Tool: apply_dns_wildcard_and_dhcp.py

## Metadata
- Nombre: apply_dns_wildcard_and_dhcp.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-07
- Descripción: Configura la regla wildcard DNS (*.admin.synology.me y admin.synology.me -> 192.168.1.100) en AdGuard Home y unifica la entrega de DNS y Gateway en DHCP en OpenWrt.
- Parámetros: Ninguno
- Dependencias: paramiko

## Código
"""

import sys
import time
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from openwrt_client import OpenWrtClient

def main():
    client = OpenWrtClient()
    client.connect()

    print("[1] Realizando backup de configuraciones en OpenWrt...")
    code, out, err = client.exec_command(
        "cp /etc/adguardhome.yaml /etc/adguardhome.yaml.bak_$(date +%Y%m%d_%H%M%S) && "
        "cp /etc/config/dhcp /etc/config/dhcp.bak_$(date +%Y%m%d_%H%M%S)",
        check_safety=False
    )
    if code != 0:
        print(f"Error creando backups: {err}")
        return 1

    print("[2] Leyendo /etc/adguardhome.yaml actual...")
    code, content, err = client.exec_command("cat /etc/adguardhome.yaml", check_safety=False)
    if code != 0:
        print(f"Error leyendo yaml: {err}")
        return 1

    # Preparar el nuevo bloque de rewrites
    old_rewrites_block = """  rewrites:
    - domain: admin.synology.me
      answer: 192.168.1.100
    - domain: labdash.admin.synology.me
      answer: 192.168.1.100
    - domain: ollama.admin.synology.me
      answer: 192.168.1.100"""

    new_rewrites_block = """  rewrites:
    - domain: '*.admin.synology.me'
      answer: 192.168.1.100
    - domain: admin.synology.me
      answer: 192.168.1.100"""

    if old_rewrites_block not in content:
        print("El bloque original de rewrites no coincide exactamente. Revisando contenido...")
        # fallback seguro: buscar 'rewrites:' y reemplazar la sección
        import re
        pattern = r"  rewrites:\n(?:    - domain:[^\n]+\n      answer:[^\n]+\n*)+"
        if re.search(pattern, content):
            content = re.sub(pattern, new_rewrites_block + "\n", content, count=1)
        else:
            print("No se pudo localizar el bloque 'rewrites:' de forma segura.")
            return 1
    else:
        content = content.replace(old_rewrites_block, new_rewrites_block, 1)

    print("[3] Deteniendo AdGuard Home temporalmente...")
    client.exec_command("/etc/init.d/adguardhome stop", check_safety=False)
    time.sleep(1)

    print("[4] Escribiendo nueva configuracion en /etc/adguardhome.yaml...")
    stdin, stdout, stderr = client.ssh.exec_command("cat > /etc/adguardhome.yaml")
    stdin.write(content)
    stdin.flush()
    stdin.channel.shutdown_write()
    err_write = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f"Error escribiendo yaml: {err_write}")
        client.exec_command("/etc/init.d/adguardhome start", check_safety=False)
        return 1

    print("[5] Iniciando AdGuard Home...")
    client.exec_command("/etc/init.d/adguardhome start", check_safety=False)
    time.sleep(2)

    print("[6] Aplicando cambios en DHCP via UCI...")
    # Unificar dhcp_option en dhcp.lan
    # Quitar 192.168.1.100 tanto de DNS (6) como de Gateway (3)
    uci_commands = [
        "uci del dhcp.lan.dhcp_option",
        "uci add_list dhcp.lan.dhcp_option='6,192.168.1.1'",
        "uci add_list dhcp.lan.dhcp_option='3,192.168.1.1'",
        "uci add_list dhcp.lan.dhcp_option='15,lan'",
        "uci commit dhcp",
        "/etc/init.d/dnsmasq restart"
    ]
    for ucmd in uci_commands:
        c, out, err = client.exec_command(ucmd, check_safety=False)
        if c != 0:
            print(f"Error ejecutando '{ucmd}': {err}")
            return 1

    print("[7] Verificando resolucion DNS en AdGuard Home...")
    domains_to_test = [
        "admin.synology.me",
        "jellyfin.admin.synology.me",
        "obsidian.admin.synology.me",
        "unifi.admin.synology.me",
        "google.com"
    ]
    for dom in domains_to_test:
        _, out, _ = client.exec_command(f"nslookup {dom} 127.0.0.1", check_safety=False)
        lines = [line.strip() for line in out.splitlines() if "Address:" in line or "Name:" in line]
        print(f"  * {dom:32} -> {', '.join(lines)}")

    print("\n[8] Verificando configuracion final de DHCP:")
    _, out, _ = client.exec_command("uci show dhcp.lan.dhcp_option", check_safety=False)
    print(out.strip())

    return 0

if __name__ == "__main__":
    sys.exit(main())
