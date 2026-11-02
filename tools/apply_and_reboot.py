"""
# Tool: apply_and_reboot.py

## Metadata
- Nombre: apply_and_reboot.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-06
- Descripción: Ejecuta reinicio controlado del router y monitorea el restablecimiento de conectividad en 192.168.1.1 vía SSH.
- Parámetros: --old-host, --new-host, --password, --timeout
- Dependencias: paramiko
"""

import argparse
import socket
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError:
    paramiko = None


def probe_port(host, port=22, timeout=2):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Reinicio y sondeo de OpenWrt")
    parser.add_argument("--old-host", default="192.168.1.1", help="IP previa del router")
    parser.add_argument("--new-host", default="192.168.1.1", help="IP restaurada del router")
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASS", ""), help="Contraseña root")
    parser.add_argument("--timeout", type=int, default=120, help="Tiempo máximo de espera en segundos")

    args = parser.parse_args()

    print(f"1. Conectando a {args.old_host} para emitir 'sync && reboot'...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_file = str(default_ed25519) if default_ed25519.exists() else None

    try:
        ssh.connect(
            hostname=args.old_host,
            port=22,
            username="root",
            password=args.password,
            key_filename=key_file,
            timeout=5,
            look_for_keys=True,
            allow_agent=True,
        )
        print("Enviando comando 'sync && reboot'...")
        ssh.exec_command("sync && reboot")
        ssh.close()
    except Exception as e:
        print(f"Nota/Aviso durante envío de reboot: {e}")

    print("Reinicio emitido. Esperando que el router complete el ciclo de booteo...")
    start_time = time.time()
    time.sleep(10)

    print(f"2. Monitoreando puerto 22 en {args.new_host}...")
    restored = False
    while time.time() - start_time < args.timeout:
        if probe_port(args.new_host, 22):
            restored = True
            print(f"\n[CONECTIVIDAD DETECTADA] Puerto SSH accesible en {args.new_host}!")
            break
        print(".", end="", flush=True)
        time.sleep(3)

    if not restored:
        print(f"\n[ALERTA] No se detectó respuesta en {args.new_host} tras {args.timeout}s.")
        print("Es posible que la tarjeta de red del equipo local requiera renovación de DHCP (ipconfig /renew).")
        sys.exit(1)

    print(f"3. Probando autenticación SSH en {args.new_host}...")
    time.sleep(3)
    ssh_new = paramiko.SSHClient()
    ssh_new.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh_new.connect(
            hostname=args.new_host,
            port=22,
            username="root",
            password=args.password,
            key_filename=key_file,
            timeout=10,
            look_for_keys=True,
            allow_agent=True,
        )
        stdin, stdout, stderr = ssh_new.exec_command("uptime && ip addr show br-lan.50")
        out = stdout.read().decode("utf-8", errors="replace")
        print(f"[SESIÓN SSH ESTABLECIDA]\n{out}")
        ssh_new.close()
    except Exception as e:
        print(f"Error conectando a {args.new_host} vía SSH: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
