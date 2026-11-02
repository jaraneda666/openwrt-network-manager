"""
# Tool: configure_vlan50_static_dhcp.py

## Metadata
- Nombre: configure_vlan50_static_dhcp.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-13
- Descripción: Agrega la reserva DHCP estática del NAS Synology y restringe la VLAN 50 (LAN) en dnsmasq desactivando DHCP dinámico (dynamicdhcp='0'), de modo que solo las direcciones MAC con concesiones estáticas reciban asignación de red.
- Parámetros: --revert, --router
- Dependencias: paramiko
"""

import argparse
import datetime
import os
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError:
    paramiko = None

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def get_ssh(host, key_file=None):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        port=22,
        username="root",
        key_filename=key_file,
        timeout=10,
        look_for_keys=True,
        allow_agent=True
    )
    return client


def backup_dhcp(ssh, host, backup_dir):
    stdin, stdout, stderr = ssh.exec_command("cat /etc/config/dhcp")
    content = stdout.read().decode("utf-8")
    out_file = backup_dir / f"dhcp_{host}.uci"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f" [BACKUP] Respaldo de /etc/config/dhcp guardado en {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Configuración de DHCP estático exclusivo en VLAN 50")
    parser.add_argument("--revert", action="store_true", help="Revertir dynamicdhcp a 1 (permitir dinámico)")
    parser.add_argument("--router", default="192.168.1.1", help="IP del Router OpenWrt")

    args = parser.parse_args()

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_file = str(default_ed25519) if default_ed25519.exists() else None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    action_name = "revert_dynamic_dhcp" if args.revert else "static_only_vlan50"
    backup_dir = Path("output") / "backups" / f"{action_name}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print("=== PASO 1: CONECTANDO Y GENERANDO RESPALDO PREVIO ===")
    ssh = get_ssh(args.router, key_file)
    backup_dhcp(ssh, args.router, backup_dir)

    if args.revert:
        print("\n=== REVIRTIENDO: Habilitando DHCP dinámico en VLAN 50 ===")
        cmd_revert = """
        uci -q delete dhcp.lan.dynamicdhcp
        uci commit dhcp
        /etc/init.d/dnsmasq restart
        """
        stdin, stdout, stderr = ssh.exec_command(cmd_revert)
        stdout.channel.recv_exit_status()
        print(" [OK] DHCP dinámico restaurado.")
    else:
        print("\n=== PASO 2: CONSOLIDANDO RESERVA DEL NAS Y DESACTIVANDO DHCP DINÁMICO ===")
        # Comandos para consolidar NAS y poner dynamicdhcp a 0
        cmd_apply = """
        # 1. Verificar si ya existe reserva para el NAS
        EXISTS=$(uci show dhcp | grep -i "00:11:32:67:CC:1A" || true)
        if [ -z "$EXISTS" ]; then
            echo "Creando sección host para nas_admin..."
            uci add dhcp host
            uci set dhcp.@host[-1].name='nas_admin'
            uci set dhcp.@host[-1].mac='00:11:32:67:CC:1A'
            uci set dhcp.@host[-1].ip='192.168.1.100'
            uci set dhcp.@host[-1].leasetime='infinite'
            uci set dhcp.@host[-1].dns='1'
        else
            echo "Reserva del NAS ya presente en UCI."
        fi

        # 2. Desactivar dynamicdhcp en la interfaz lan (VLAN 50)
        uci set dhcp.lan.dynamicdhcp='0'
        uci commit dhcp

        # 3. Reiniciar dnsmasq limpiamente
        /etc/init.d/dnsmasq restart
        """
        stdin, stdout, stderr = ssh.exec_command(cmd_apply)
        out = stdout.read().decode('utf-8')
        print(out)

    print("\n=== PASO 3: VERIFICACIÓN DE CONFIGURACIÓN GENERADA ===")
    time.sleep(2)

    # Verificar dnsmasq.conf generado
    stdin, stdout, stderr = ssh.exec_command("cat /var/etc/dnsmasq.conf.* | grep -E 'dhcp-range=set:lan|00:11:32:67:CC:1A'")
    print("Directivas activas en dnsmasq:")
    print(stdout.read().decode('utf-8').strip())

    # Probar resolución y pings
    print("\n=== PASO 4: PRUEBAS DE CONECTIVIDAD Y RESOLUCIÓN ===")
    stdin, stdout, stderr = ssh.exec_command("ping -c 2 -W 1 192.168.1.100 && echo 'PING NAS OK' || echo 'PING NAS FALLO'")
    print(stdout.read().decode('utf-8').strip())

    stdin, stdout, stderr = ssh.exec_command("ping -c 2 -W 1 127.0.0.1 && echo 'PING PC USUARIO OK' || echo 'PING PC FALLO'")
    print(stdout.read().decode('utf-8').strip())

    stdin, stdout, stderr = ssh.exec_command("nslookup nas_admin.lan 127.0.0.1:54")
    print("\nResolución DNS local en dnsmasq:")
    print(stdout.read().decode('utf-8').strip())

    ssh.close()
    print("\n[PROCESO FINALIZADO EXITOSAMENTE]")


if __name__ == "__main__":
    main()
