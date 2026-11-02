"""
# Tool: restore_backup.py

## Metadata
- Nombre: restore_backup.py
- Versión: 1.1
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-06
- Descripción: Sube y aplica un archivo de respaldo .tar.gz de OpenWrt enviándolo por stdin a sysupgrade -r - vía SSH sin requerir SFTP.
- Parámetros: --host, --port, --user, --password, --backup-path
- Dependencias: paramiko
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    paramiko = None


def main():
    parser = argparse.ArgumentParser(description="Restaurador seguro de backup OpenWrt")
    parser.add_argument("--host", default="192.168.1.1", help="Dirección IP actual del router")
    parser.add_argument("--port", default=22, type=int, help="Puerto SSH")
    parser.add_argument("--user", default="root", help="Usuario SSH")
    parser.add_argument("--password", default=None, help="Contraseña")
    parser.add_argument("--backup-path", required=True, help="Ruta al archivo .tar.gz de respaldo")

    args = parser.parse_args()

    backup_file = Path(args.backup_path)
    if not backup_file.exists():
        print(f"Error: No existe el archivo de backup en {backup_file}")
        sys.exit(1)

    backup_bytes = backup_file.read_bytes()
    print(f"Leyendo backup local: {backup_file.name} ({len(backup_bytes)} bytes)")

    print(f"Conectando a {args.host}:{args.port}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_file = str(default_ed25519) if default_ed25519.exists() else None

    ssh.connect(
        hostname=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        key_filename=key_file,
        timeout=10,
        look_for_keys=True,
        allow_agent=True,
    )

    print("Enviando archivo por stdin a 'sysupgrade -r -'...")
    stdin, stdout, stderr = ssh.exec_command("sysupgrade -r -")
    stdin.write(backup_bytes)
    stdin.flush()
    stdin.channel.shutdown_write()

    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()

    print(f"Código de salida: {code}")
    if out:
        print(f"Salida:\n{out}")
    if err:
        print(f"Error:\n{err}")

    if code == 0:
        print("[RESTAURACIÓN EXITOSA] Archivos restaurados correctamente en el router.")
    else:
        print("[ERROR] Falló la restauración del backup.")
        sys.exit(code)

    ssh.close()


if __name__ == "__main__":
    main()
