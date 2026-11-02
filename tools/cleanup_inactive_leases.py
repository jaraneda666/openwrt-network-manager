"""
# Tool: cleanup_inactive_leases.py

## Metadata
- Nombre: cleanup_inactive_leases.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-09
- Descripción: Purga de /tmp/dhcp.leases las asignaciones dinámicas y obsoletas de equipos no conectados, preservando las reservas estáticas de UCI y los registros DNS.
- Parámetros: ninguno
- Dependencias: subprocess, paramiko o ssh estándar
"""

import subprocess
import re
import sys

ROUTER_IP = "192.168.1.1"

def run_ssh(cmd):
    res = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", f"root@{ROUTER_IP}", cmd],
        capture_output=True,
        text=True
    )
    return res.stdout.strip()

def main():
    print("1. Respaldando /tmp/dhcp.leases en el router...")
    ts = run_ssh("date +%Y%m%d_%H%M%S")
    run_ssh(f"cp /tmp/dhcp.leases /tmp/dhcp.leases.bak_{ts}")
    print(f"  Respaldo creado: /tmp/dhcp.leases.bak_{ts}")

    # MACs activas confirmadas
    active_macs = {
        "30:56:0f:a8:a8:4c", # admin-casa (127.0.0.1)
        "34:93:42:88:2b:28", # admin-tv (192.168.2.4)
        "e0:63:da:27:66:82", # sw-casa (192.168.1.252)
        "6c:5a:b5:58:03:68", # google-home (192.168.1.7)
        "a4:e5:7c:9b:4f:fc", # Next_control (192.168.1.1000)
        "cc:4d:75:75:14:7d", # xiaomi-vacuum (192.168.2.186)
        "b6:37:f6:22:17:8f", # admin_movil (192.168.1.1004)
    }

    raw_leases = run_ssh("cat /tmp/dhcp.leases")
    kept_lines = []
    removed_count = 0

    print("\n2. Analizando leases actuales:")
    for line in raw_leases.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            mac = parts[1].lower()
            ip = parts[2]
            host = parts[3]
            if mac in active_macs:
                kept_lines.append(line)
                print(f"  [CONECTADO - CONSERVADO] {ip:16} {mac} ({host})")
            else:
                removed_count += 1
                print(f"  [DESCONECTADO - ELIMINADO]  {ip:16} {mac} ({host})")

    print(f"\nTotal eliminados de la lista activa: {removed_count}")
    print(f"Total conservados (en línea): {len(kept_lines)}")

    # Escribir nuevo contenido
    new_content = "\n".join(kept_lines) + "\n"
    
    print("\n3. Aplicando lista depurada en /tmp/dhcp.leases y reiniciando dnsmasq...")
    # Detener dnsmasq, actualizar archivo y arrancar dnsmasq
    write_cmd = f"cat << 'EOF' > /tmp/dhcp.leases\n{new_content}EOF\n/etc/init.d/dnsmasq restart"
    run_ssh(write_cmd)

    print("\n4. Verificando estado final de /tmp/dhcp.leases en el router:")
    final_leases = run_ssh("cat /tmp/dhcp.leases")
    print(final_leases)

    print("\n5. Validando resolución DNS de equipos desconectados con reserva estática:")
    test_hosts = ["pc_emma.lan", "pc-amanda.lan", "tv-dormitorio.lan", "tablet-amanda.lan", "iphone-amanda.lan"]
    for th in test_hosts:
        res = run_ssh(f"nslookup {th} 127.0.0.1 2>/dev/null | grep Address | tail -n 1")
        print(f"  {th:22} -> {res}")

if __name__ == "__main__":
    main()
