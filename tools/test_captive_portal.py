"""
# Tool: test_captive_portal.py

## Metadata
- Nombre: test_captive_portal.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-09
- Descripción: Verifica el estado del portal cautivo openNDS en VLAN 70 (GUEST), clientes autenticados, timeouts de 30 minutos y reglas de nftables asociadas.
- Parámetros: ninguno
- Dependencias: subprocess, ssh
"""

import subprocess
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
    print("=== ESTADO DEL PORTAL CAUTIVO (openNDS) EN OPENWRT ===")
    status = run_ssh("ndsctl status")
    print(status)

    print("\n=== CLIENTES ACTIVOS EN PORTAL ===")
    json_clients = run_ssh("ndsctl json")
    print(json_clients)

    print("\n=== REGLAS NFTABLES DE REDIRECCIÓN Y FILTRADO ===")
    nat_rules = run_ssh("nft list table ip nds_nat")
    print(nat_rules)

if __name__ == "__main__":
    main()
