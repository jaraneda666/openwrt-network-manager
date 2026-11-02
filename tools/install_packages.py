"""
# Tool: install_packages.py

## Metadata
- Nombre: install_packages.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-06
- Descripción: Instala por lotes los paquetes aprobados vía opkg en OpenWrt y valida servicios.
- Parámetros: --host, --port, --user
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


PACKAGES = [
    "luci-app-sqm",
    "igmpproxy",
    "socat",
    "adguardhome",
    "luci-app-banip",
    "luci-app-wifischedule",
    "luci-app-samba4",
    "luci-app-upnp",
    "luci-app-hd-idle",
    "luci-app-openvpn",
    "openvpn-easy-rsa",
    "luci-app-sshtunnel",
    "luci-app-statistics",
    "luci-app-watchcat",
    "luci-app-attendedsysupgrade",
    "luci-app-acme",
    "mc",
]


def main():
    parser = argparse.ArgumentParser(description="Instalador seguro de paquetes OpenWrt")
    parser.add_argument("--host", default="192.168.1.1", help="IP del router")
    parser.add_argument("--port", default=22, type=int, help="Puerto SSH")
    parser.add_argument("--user", default="root", help="Usuario SSH")

    args = parser.parse_args()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_file = str(default_ed25519) if default_ed25519.exists() else None

    print(f"Conectando a {args.host}:{args.port} vía SSH...")
    ssh.connect(
        hostname=args.host,
        port=args.port,
        username=args.user,
        key_filename=key_file,
        timeout=10,
        look_for_keys=True,
        allow_agent=True,
    )

    # 1. Asegurar repositorio actualizado
    print("Actualizando listas de opkg (opkg update)...")
    stdin, stdout, stderr = ssh.exec_command("opkg update")
    stdout.channel.recv_exit_status()

    # 2. Instalar paquetes en lote
    pkg_str = " ".join(PACKAGES)
    print(f"Instalando {len(PACKAGES)} paquetes: {pkg_str}")
    cmd_install = f"opkg install {pkg_str}"
    stdin, stdout, stderr = ssh.exec_command(cmd_install, timeout=300)
    
    while not stdout.channel.exit_status_ready():
        line = stdout.readline()
        if line:
            print(line.strip())
        time.sleep(0.1)

    code = stdout.channel.recv_exit_status()
    print(f"\nFinalizada instalación con código: {code}")

    # 3. Deshabilitar DAWN si existiera residuo
    ssh.exec_command("/etc/init.d/dawn disable 2>/dev/null ; /etc/init.d/dawn stop 2>/dev/null")

    # 4. Verificar espacio disponible y servicios instalados
    stdin, stdout, stderr = ssh.exec_command("df -h / && echo '--- SERVICIOS INIT ---' && ls /etc/init.d/")
    out = stdout.read().decode("utf-8", errors="replace")
    print("\nEstado final del sistema:")
    print(out)

    ssh.close()


if __name__ == "__main__":
    main()
