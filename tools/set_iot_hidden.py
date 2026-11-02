"""
# Tool: set_iot_hidden.py

## Metadata
- Nombre: set_iot_hidden.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-13
- Descripción: Aplica o revierte la opción hidden='1' al SSID Casa_IoT en los Access Points y Router OpenWrt con respaldo previo, recarga el subsistema Wi-Fi y monitorea en vivo la asociación y estabilidad de los dispositivos IoT.
- Parámetros: --revert, --duration, --router, --ap1, --ap2
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


def backup_wireless(ssh, host, backup_dir):
    stdin, stdout, stderr = ssh.exec_command("cat /etc/config/wireless")
    content = stdout.read().decode("utf-8")
    out_file = backup_dir / f"wireless_{host}.uci"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f" [BACKUP] Respaldo de /etc/config/wireless de {host} guardado en {out_file}")


def apply_hidden(ssh, host, revert=False):
    if revert:
        cmd = """
        uci -q delete wireless.ap_iot.hidden
        uci commit wireless
        wifi reload
        """
        action = "REVERTIR (Hacer visible)"
    else:
        cmd = """
        uci set wireless.ap_iot.hidden='1'
        uci commit wireless
        wifi reload
        """
        action = "APLICAR (Ocultar SSID)"

    print(f" -> Ejecutando {action} en {host}...")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        err = stderr.read().decode('utf-8')
        print(f" [ERROR] Fallo en {host}: {err}")
    else:
        print(f" [OK] Configuración actualizada y 'wifi reload' disparado en {host}.")


def main():
    parser = argparse.ArgumentParser(description="Ocultar o hacer visible el SSID Casa_IoT con monitoreo")
    parser.add_argument("--revert", action="store_true", help="Revertir el SSID Casa_IoT a visible")
    parser.add_argument("--duration", type=int, default=60, help="Duración del monitoreo en segundos")
    parser.add_argument("--router", default="192.168.1.1", help="IP del Router")
    parser.add_argument("--ap1", default="192.168.1.253", help="IP del AP1")
    parser.add_argument("--ap2", default="192.168.1.254", help="IP del AP2")

    args = parser.parse_args()

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_file = str(default_ed25519) if default_ed25519.exists() else None

    # Directorio de respaldo
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    action_name = "revert_visible_iot" if args.revert else "hidden_iot"
    backup_dir = Path("output") / "backups" / f"{action_name}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    hosts = [args.router, args.ap1, args.ap2]

    # Paso 1: Respaldos
    print("\n=== PASO 1: GENERANDO RESPALDOS PREVIOS DE WIRELESS ===")
    ssh_clients = {}
    for h in hosts:
        client = get_ssh(h, key_file)
        ssh_clients[h] = client
        backup_wireless(client, h, backup_dir)

    # Paso 2: Aplicación
    print(f"\n=== PASO 2: {'REVIRTIENDO A VISIBLE' if args.revert else 'OCULTANDO SSID Casa_IoT'} ===")
    # En el router solo uci (los radios están desactivados, pero mantenemos consistencia)
    r_ssh = ssh_clients[args.router]
    if args.revert:
        r_ssh.exec_command("uci -q delete wireless.ap_iot.hidden && uci commit wireless")
    else:
        r_ssh.exec_command("uci set wireless.ap_iot.hidden='1' && uci commit wireless")
    print(f" [OK] Router {args.router} actualizado en UCI.")

    # En los APs aplicamos y recargamos wifi
    for ap in [args.ap1, args.ap2]:
        apply_hidden(ssh_clients[ap], ap, revert=args.revert)

    # Paso 3: Monitoreo en vivo
    print(f"\n=== PASO 3: MONITOREO DE CONECTIVIDAD IoT (duración: {args.duration}s) ===")
    vacuum_mac = "cc:4d:75:75:14:7d"
    vacuum_ip = "192.168.2.186"
    tv_ip = "192.168.2.4"

    start_time = time.time()
    poll_count = 0

    while time.time() - start_time < args.duration:
        poll_count += 1
        elapsed = int(time.time() - start_time)
        print(f"\n--- Sondeo #{poll_count} (+{elapsed}s) ---")

        # Verificar asociación en AP1 y AP2
        assoc_info = None
        ap_connected = None
        for ap_name, ap_host in [("AP1 (Salón)", args.ap1), ("AP2 (Habitaciones)", args.ap2)]:
            _, out, _ = ssh_clients[ap_host].exec_command(f"iwinfo phy1-ap2 assoclist | grep -i '{vacuum_mac}'")
            line = out.read().decode('utf-8').strip()
            if line:
                assoc_info = line
                ap_connected = ap_name
                break

        if assoc_info:
            print(f"  [Wi-Fi Aspiradora]: ASOCIADA a {ap_connected}")
            print(f"    -> Detalle: {assoc_info}")
        else:
            print("  [Wi-Fi Aspiradora]: No asociada en este instante (renegociando enlace)...")

        # Ping desde router a aspiradora
        _, out_ping, _ = ssh_clients[args.router].exec_command(f"ping -c 1 -W 1 {vacuum_ip} > /dev/null && echo OK || echo NO_REPLY")
        ping_res = out_ping.read().decode('utf-8').strip()
        print(f"  [Ping Aspiradora {vacuum_ip}]: {ping_res}")

        # Ping a Smart TV (cableada en VLAN 60) como testigo
        _, out_tv, _ = ssh_clients[args.router].exec_command(f"ping -c 1 -W 1 {tv_ip} > /dev/null && echo OK || echo NO_REPLY")
        tv_res = out_tv.read().decode('utf-8').strip()
        print(f"  [Ping Smart TV {tv_ip} (Testigo VLAN 60)]: {tv_res}")

        # Si ya está conectada y respondiendo ping tras los primeros 15s, podemos verificar señal y estado
        time.sleep(5)

    print("\n=== PASO 4: VERIFICACIÓN FINAL Y ESTADO DE INTERFACES ===")
    for ap_name, ap_host in [("AP1", args.ap1), ("AP2", args.ap2)]:
        _, out, _ = ssh_clients[ap_host].exec_command("iwinfo phy1-ap2 info | grep -E 'ESSID|Access Point|Mode|Channel'")
        info = out.read().decode('utf-8').strip()
        print(f"Estado interfaz phy1-ap2 en {ap_name} ({ap_host}):\n{info}\n")

    # Cerrar conexiones
    for client in ssh_clients.values():
        client.close()

    print("[PROCESO COMPLETADO]")


if __name__ == "__main__":
    main()
