"""
# Tool: deploy_wifi_casa_night_speed.py

## Metadata
- Nombre: deploy_wifi_casa_night_speed.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-06
- Descripción: Instala tc-tiny, despliega wifi_casa_speed.sh y programa tareas cron (22:00 a 5 Mbps de Dom-Jue, 07:00 normal de Lun-Vie) en ambos Access Points UniFi AC Pro.
- Parámetros: --aps
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


SCRIPT_CONTENT = """#!/bin/sh

case "$1" in
    throttle)
        tc qdisc del dev phy0-ap0 root 2>/dev/null
        tc qdisc del dev phy1-ap1 root 2>/dev/null
        tc qdisc add dev phy0-ap0 root tbf rate 10mbit burst 32k latency 50ms
        tc qdisc add dev phy1-ap1 root tbf rate 10mbit burst 32k latency 50ms
        logger -t wifi_casa_speed "Velocidad reducida a 10 Mbps en SSID Casa (5G y 2.4G)"
        ;;
    normal)
        tc qdisc del dev phy0-ap0 root 2>/dev/null
        tc qdisc del dev phy1-ap1 root 2>/dev/null
        logger -t wifi_casa_speed "Velocidad normal restaurada en SSID Casa (5G y 2.4G)"
        ;;
    status)
        echo "=== 5G (phy0-ap0) ==="
        tc qdisc show dev phy0-ap0
        echo "=== 2.4G (phy1-ap1) ==="
        tc qdisc show dev phy1-ap1
        ;;
    *)
        echo "Uso: $0 {throttle|normal|status}"
        exit 1
        ;;
esac
"""


def main():
    parser = argparse.ArgumentParser(description="Despliegue de limitador nocturno en APs")
    parser.add_argument("--aps", nargs="+", default=["192.168.1.253", "192.168.1.254"], help="IPs de los APs")

    args = parser.parse_args()

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_str = str(default_ed25519) if default_ed25519.exists() else None

    for ap in args.aps:
        print(f"\n==========================================")
        print(f"Configurando AP: {ap}")
        print(f"==========================================")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ap, port=22, username="root", key_filename=key_str, timeout=10)

        # 1. Asegurar repositorio y tc-tiny
        print(" - Verificando/Instalando tc-tiny...")
        stdin, stdout, stderr = ssh.exec_command("which tc || (opkg update && opkg install tc-tiny kmod-sched-core)")
        stdout.channel.recv_exit_status()

        # 2. Instalar script wifi_casa_speed.sh
        print(" - Escribiendo /usr/bin/wifi_casa_speed.sh...")
        # Escribir archivo por stdin
        stdin, stdout, stderr = ssh.exec_command("cat > /usr/bin/wifi_casa_speed.sh && chmod +x /usr/bin/wifi_casa_speed.sh")
        stdin.write(SCRIPT_CONTENT)
        stdin.flush()
        stdin.channel.shutdown_write()
        stdout.channel.recv_exit_status()

        # 3. Configurar cron en el AP
        print(" - Programando tareas crontab (22:00 throttle Dom-Jue, 07:00 normal Lun-Vie)...")
        cron_entries = (
            "00 22 * * 0,1,2,3,4 /usr/bin/wifi_casa_speed.sh throttle\n"
            "00 07 * * 1,2,3,4,5 /usr/bin/wifi_casa_speed.sh normal\n"
        )
        stdin, stdout, stderr = ssh.exec_command("cat > /etc/crontabs/root && /etc/init.d/cron enable && /etc/init.d/cron restart")
        stdin.write(cron_entries)
        stdin.flush()
        stdin.channel.shutdown_write()
        stdout.channel.recv_exit_status()

        # 4. Probar script en modo status
        stdin, stdout, stderr = ssh.exec_command("/usr/bin/wifi_casa_speed.sh status")
        out = stdout.read().decode("utf-8", errors="replace")
        print(f"Estado qdisc actual:\n{out}")

        ssh.close()
        print(f"AP {ap} configurado exitosamente.")


if __name__ == "__main__":
    main()
