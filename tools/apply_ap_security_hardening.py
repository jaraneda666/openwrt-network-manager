"""
# Tool: apply_ap_security_hardening.py

## Metadata
- Nombre: apply_ap_security_hardening.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-07
- Descripción: Aplica hardening de SSH en los Access Points OpenWrt (192.168.1.253 y 192.168.1.254) deshabilitando autenticación por contraseña para root y forzando autenticación exclusiva por clave pública Ed25519.
- Parámetros: Ninguno
- Dependencias: paramiko

## Código
"""

import sys
import time
from pathlib import Path
import paramiko

def harden_ap(ip, key_file):
    print(f"\n==========================================")
    print(f"Aplicando Hardening en AP: {ip}")
    print(f"==========================================")

    # 1. Connect via Key
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, 22, username="root", key_filename=key_file, timeout=5)

    # Check authorized keys before touching anything
    _, out, _ = ssh.exec_command("cat /etc/dropbear/authorized_keys 2>/dev/null")
    keys = out.read().decode().strip().splitlines()
    if not keys:
        ssh.close()
        raise RuntimeError(f"ABORTADO: {ip} no tiene authorized_keys configurado. Riesgo de bloqueo!")

    print(f"[1] Claves autorizadas verificadas ({len(keys)} encontrada/s).")

    # Backup current dropbear config
    ssh.exec_command("cp /etc/config/dropbear /etc/config/dropbear.bak_$(date +%Y%m%d_%H%M%S)")
    print("[2] Respaldo de /etc/config/dropbear creado.")

    # Apply hardening via UCI
    commands = [
        "uci set dropbear.main.PasswordAuth='off'",
        "uci set dropbear.main.RootPasswordAuth='off'",
        "uci commit dropbear",
        "/etc/init.d/dropbear restart"
    ]
    for cmd in commands:
        code = ssh.exec_command(cmd)[1].channel.recv_exit_status()
        if code != 0:
            ssh.close()
            raise RuntimeError(f"Error ejecutando '{cmd}' en {ip}")

    print("[3] Configuracion UCI aplicada y Dropbear reiniciado.")
    ssh.close()
    time.sleep(2)

    # 2. Verify Key Auth STILL WORKS
    print("[4] Verificando acceso autenticado por clave Ed25519...")
    ssh_verify = paramiko.SSHClient()
    ssh_verify.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_verify.connect(ip, 22, username="root", key_filename=key_file, timeout=5)
    _, out, _ = ssh_verify.exec_command("whoami; uci show dropbear.main")
    print("Salida de verificacion:")
    print(out.read().decode().strip())
    ssh_verify.close()
    print(f" [OK] AP {ip} protegido exitosamente.")

def main():
    key_file = str(Path.home() / ".ssh" / "id_ed25519")
    aps = ["192.168.1.253", "192.168.1.254"]

    for ap in aps:
        try:
            harden_ap(ap, key_file)
        except Exception as e:
            print(f"[ERROR] en {ap}: {e}")
            return 1

    print("\n[PROCESO COMPLETADO EXITOSAMENTE EN AMBOS APs]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
