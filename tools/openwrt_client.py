"""
# Tool: openwrt_client.py

## Metadata
- Nombre: openwrt_client.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-05
- Descripción: Cliente de automatización y administración segura para routers OpenWrt vía SSH/SFTP con verificación previa de conectividad, extracción obligatoria de backups (sysupgrade y /etc/config) y ejecución controlada de comandos UCI.
- Parámetros: --host, --port, --user, --password, --action (test, status, backup, get-config, exec, uci), --cmd, --config-name, --out-dir
- Dependencias: paramiko

## Código
"""

import argparse
import datetime
import os
import socket
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import paramiko
except ImportError:
    paramiko = None


class OpenWrtClient:
    """Cliente para administración y respaldo seguro de OpenWrt."""

    def __init__(self, host="192.168.1.1", port=22, user="root", password=None, key_filename=None):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password or os.environ.get("OPENWRT_PASSWORD", os.environ.get("ADMIN_PASS", ""))
        self.key_filename = key_filename
        self.ssh = None

    def test_tcp_connectivity(self, timeout=3):
        """Verifica disponibilidad TCP del puerto SSH."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((self.host, self.port))
            sock.close()
            return True, f"Puerto SSH {self.port} en {self.host} accesible."
        except Exception as e:
            return False, f"Fallo al conectar a {self.host}:{self.port} -> {e}"

    def connect(self):
        """Establece sesión SSH con el router."""
        if not paramiko:
            raise RuntimeError("Biblioteca 'paramiko' no instalada. Ejecute 'pip install paramiko'.")

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_file = self.key_filename
        if not key_file:
            default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
            default_rsa = Path.home() / ".ssh" / "id_rsa"
            if default_ed25519.exists():
                key_file = str(default_ed25519)
            elif default_rsa.exists():
                key_file = str(default_rsa)

        self.ssh.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            key_filename=key_file,
            timeout=10,
            look_for_keys=True,
            allow_agent=True,
        )
        return True

    def close(self):
        """Cierra la conexión SSH activa."""
        if self.ssh:
            self.ssh.close()
            self.ssh = None

    def exec_command(self, command, check_safety=True):
        """
        Ejecuta un comando remoto por SSH con validaciones de seguridad.
        """
        if check_safety:
            low = command.lower()
            dangerous_patterns = ["reboot", "poweroff", "init 6", "firstboot", "mtd erase", "dd if="]
            for dp in dangerous_patterns:
                if dp in low:
                    raise PermissionError(
                        f"Comando de alto riesgo detectado ('{dp}'). Requiere confirmación explícita."
                    )

        if not self.ssh:
            self.connect()

        stdin, stdout, stderr = self.ssh.exec_command(command, timeout=30)
        out_text = stdout.read().decode("utf-8", errors="replace")
        err_text = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        return exit_code, out_text, err_text

    def get_system_status(self):
        """Recupera información técnica de hardware, OS y recursos del router."""
        cmd = (
            "echo '--- RELEASE ---' && cat /etc/openwrt_release 2>/dev/null && "
            "echo '--- UPTIME ---' && uptime && "
            "echo '--- MEMORY ---' && free && "
            "echo '--- DISK ---' && df -h / && "
            "echo '--- NETWORK INTERFACES ---' && ifconfig"
        )
        code, out, err = self.exec_command(cmd, check_safety=False)
        return out

    def perform_backup(self, output_dir):
        """
        Genera y descarga un respaldo integral:
        1. Archivo .tar.gz mediante 'sysupgrade -b'
        2. Extracción de todos los archivos de /etc/config/ en texto plano
        """
        if not self.ssh:
            self.connect()

        out_path = Path(output_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = out_path / f"backup_{timestamp}"
        target_dir.mkdir(parents=True, exist_ok=True)

        config_dir = target_dir / "etc_config"
        config_dir.mkdir(parents=True, exist_ok=True)

        # 1. Sysupgrade backup via streaming binario
        remote_tar = f"/tmp/backup_{timestamp}.tar.gz"
        local_tar = target_dir / f"sysupgrade_backup_{timestamp}.tar.gz"

        # Generar archivo en router y volcarlo a stdout
        cmd_sys = f"sysupgrade -b {remote_tar} >/dev/null 2>&1 && cat {remote_tar} && rm -f {remote_tar}"
        stdin, stdout, stderr = self.ssh.exec_command(cmd_sys)
        tar_bytes = stdout.read()
        err_text = stderr.read().decode("utf-8", errors="replace")

        if not tar_bytes or len(tar_bytes) < 100:
            raise RuntimeError(f"Error generando sysupgrade backup en router: {err_text}")

        local_tar.write_bytes(tar_bytes)

        # 2. Descarga de archivos de /etc/config via tar stream
        cmd_cfg = "tar -cz -C /etc/config ."
        stdin_c, stdout_c, stderr_c = self.ssh.exec_command(cmd_cfg)
        cfg_bytes = stdout_c.read()

        import io
        import tarfile
        import hashlib

        if cfg_bytes:
            buf = io.BytesIO(cfg_bytes)
            with tarfile.open(fileobj=buf, mode="r:gz") as tar:
                tar.extractall(path=config_dir)

        # 3. Listado de paquetes instalados
        code_pkg, pkg_out, _ = self.exec_command("opkg list-installed", check_safety=False)
        pkg_file = target_dir / "installed_packages.txt"
        if code_pkg == 0 and pkg_out:
            pkg_file.write_text(pkg_out, encoding="utf-8")

        sha256_hash = hashlib.sha256(tar_bytes).hexdigest()

        # Generar manifiesto del respaldo
        manifest_file = target_dir / "MANIFEST.txt"
        manifest_file.write_text(
            f"OpenWrt Backup Manifest\n"
            f"Fecha: {datetime.datetime.now().isoformat()}\n"
            f"Host: {self.host}\n"
            f"Archivo Sysupgrade: {local_tar.name} ({len(tar_bytes)} bytes)\n"
            f"SHA256 Sysupgrade: {sha256_hash}\n"
            f"Archivos /etc/config extraídos: {len(list(config_dir.glob('*')))} archivos\n"
            f"Paquetes instalados registrados: {len(pkg_out.splitlines()) if code_pkg == 0 else 0} paquetes\n",
            encoding="utf-8",
        )

        return target_dir

    def get_uci_config(self, config_name):
        """Obtiene la configuración completa de un paquete UCI (ej. network, wireless, firewall)."""
        code, out, err = self.exec_command(f"uci export {config_name}", check_safety=False)
        if code != 0:
            return None, err
        return out, None


def main():
    parser = argparse.ArgumentParser(description="Gestor y cliente seguro OpenWrt")
    parser.add_argument("action", choices=["test", "status", "backup", "get-config", "exec", "uci"], help="Acción a ejecutar")
    parser.add_argument("--host", default="192.168.1.1", help="Dirección IP del router")
    parser.add_argument("--port", default=22, type=int, help="Puerto SSH")
    parser.add_argument("--user", default="root", help="Usuario de acceso")
    parser.add_argument("--password", default=None, help="Contraseña (opcional, o variable OPENWRT_PASSWORD)")
    parser.add_argument("--out-dir", default="./output/backups", help="Directorio de salida para respaldos")
    parser.add_argument("--config-name", default="network", help="Nombre del paquete UCI para get-config")
    parser.add_argument("--cmd", default="", help="Comando a ejecutar para action=exec")
    parser.add_argument("--force", action="store_true", help="Omitir validación de seguridad si fue autorizado por el usuario")

    args = parser.parse_args()
    client = OpenWrtClient(host=args.host, port=args.port, user=args.user, password=args.password)

    if args.action == "test":
        ok, msg = client.test_tcp_connectivity()
        print(f"[TEST CONECTIVIDAD] {'OK' if ok else 'FALLO'}: {msg}")
        if ok:
            try:
                client.connect()
                print("[TEST AUTENTICACIÓN] SSH Autenticación exitosa.")
                client.close()
            except Exception as e:
                print(f"[TEST AUTENTICACIÓN] FALLO: {e}")
                sys.exit(1)

    elif args.action == "status":
        client.connect()
        try:
            status = client.get_system_status()
            print(status)
        finally:
            client.close()

    elif args.action == "backup":
        print(f"Iniciando respaldo completo de {args.host}...")
        client.connect()
        try:
            backup_folder = client.perform_backup(args.out_dir)
            print(f"[BACKUP COMPLETADO] Guardado en: {backup_folder}")
        finally:
            client.close()

    elif args.action == "get-config":
        client.connect()
        try:
            cfg, err = client.get_uci_config(args.config_name)
            if err:
                print(f"Error: {err}")
            else:
                print(cfg)
        finally:
            client.close()

    elif args.action == "exec":
        if not args.cmd:
            print("Error: Debe especificar un comando con --cmd.")
            sys.exit(1)
        client.connect()
        try:
            code, out, err = client.exec_command(args.cmd, check_safety=not args.force)
            print(f"Exit Code: {code}")
            if out:
                print(f"Stdout:\n{out}")
            if err:
                print(f"Stderr:\n{err}")
        finally:
            client.close()


if __name__ == "__main__":
    main()

"""
## Uso
```bash
# Probar conectividad y autenticación
python openwrt_client.py test --host 192.168.1.1

# Consultar estado general del router
python openwrt_client.py status

# Ejecutar respaldo integral previo a cambios
python openwrt_client.py backup --out-dir ./output/backups

# Exportar configuración de red o firewall
python openwrt_client.py get-config --config-name firewall
```
"""
