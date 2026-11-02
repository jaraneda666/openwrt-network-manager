"""
# Tool: apply_mac_whitelist_firewall.py

## Metadata
- Nombre: apply_mac_whitelist_firewall.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-13
- Descripción: Extrae las direcciones MAC autorizadas desde las reservas estáticas de UCI DHCP (/etc/config/dhcp) y configura una regla en OpenWrt fw4 (nftables) que descarta (DROP) todo el tráfico proveniente de la LAN hacia Internet (WAN) si la dirección MAC de origen no pertenece a la lista blanca.
- Parámetros: --router, --dry-run, --revert, --include-leases, --extra-macs
- Dependencias: paramiko

## Código
"""

import argparse
import datetime
import os
import re
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
    if not paramiko:
        raise RuntimeError("La librería paramiko es requerida para ejecutar este script.")
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


def run_cmd(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code


def backup_firewall(ssh, host, backup_dir):
    out, err, code = run_cmd(ssh, "cat /etc/config/firewall")
    if code != 0:
        raise RuntimeError(f"Error al obtener respaldo de firewall: {err}")
    out_file = backup_dir / f"firewall_{host}.uci"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(out)
    print(f" [BACKUP] Respaldo de /etc/config/firewall guardado en: {out_file}")
    return out_file


def extract_static_macs(ssh):
    out, err, code = run_cmd(ssh, "uci show dhcp")
    if code != 0:
        raise RuntimeError(f"Error al consultar uci show dhcp: {err}")

    hosts = {}
    for line in out.splitlines():
        if line.startswith("dhcp.@host["):
            parts = line.split("=")
            key = parts[0].strip()
            val = parts[1].strip("'\"") if len(parts) > 1 else ""
            sec_match = re.search(r"dhcp\.@host\[(\d+)\]", key)
            if not sec_match:
                continue
            idx = int(sec_match.group(1))
            if idx not in hosts:
                hosts[idx] = {"macs": []}
            if ".mac=" in line or ".mac[" in line:
                found_macs = re.findall(r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", val)
                hosts[idx]["macs"].extend([m.lower() for m in found_macs])
            elif ".name=" in line:
                hosts[idx]["name"] = val
            elif ".ip=" in line:
                hosts[idx]["ip"] = val

    valid_macs = {}
    for idx, data in sorted(hosts.items()):
        name = data.get("name", f"host_{idx}")
        ip = data.get("ip", "N/A")
        for mac in data.get("macs", []):
            valid_macs[mac] = {
                "name": name,
                "ip": ip
            }
    return valid_macs


def extract_active_leases(ssh):
    out, err, code = run_cmd(ssh, "cat /tmp/dhcp.leases")
    leases = {}
    if code == 0:
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 4:
                mac = parts[1].lower()
                ip = parts[2]
                hostname = parts[3]
                if re.match(r"^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", mac):
                    leases[mac] = {"name": hostname, "ip": ip}
    return leases


def main():
    parser = argparse.ArgumentParser(
        description="Aplica regla de lista blanca MAC en fw4 para salida a Internet"
    )
    parser.add_argument("--router", default="192.168.1.1", help="IP del Router OpenWrt")
    parser.add_argument("--dry-run", action="store_true", help="Solo simula y muestra la regla generada")
    parser.add_argument("--revert", action="store_true", help="Elimina la regla y revierte a comportamiento normal")
    parser.add_argument("--include-leases", action="store_true", help="Incluye también las MACs activas en /tmp/dhcp.leases")
    parser.add_argument("--extra-macs", nargs="*", default=[], help="Lista de MACs adicionales a autorizar")

    args = parser.parse_args()

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_file = str(default_ed25519) if default_ed25519.exists() else None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    action_type = "revert_mac_whitelist" if args.revert else "apply_mac_whitelist"
    backup_dir = Path("output") / "backups" / f"{action_type}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== PASO 1: CONEXIÓN SSH CON EL ROUTER ({args.router}) ===")
    ssh = get_ssh(args.router, key_file)
    print(" [OK] Conexión establecida con éxito.")

    backup_firewall(ssh, args.router, backup_dir)

    if args.revert:
        print("\n=== REVIRTIENDO: ELIMINANDO REGLA Drop_Non_Whitelisted_LAN_WAN ===")
        cmd_revert = """
        uci -q delete firewall.drop_unknown_mac
        uci commit firewall
        /sbin/fw4 reload
        """
        out, err, code = run_cmd(ssh, cmd_revert)
        if code == 0:
            print(" [OK] Regla eliminada y firewall recargado exitosamente.")
        else:
            print(f" [ERROR] Fallo al recargar firewall: {err}")
        return

    print("\n=== PASO 2: EXTRACCIÓN Y AUDITORÍA DE DIRECCIONES MAC ===")
    mac_dict = extract_static_macs(ssh)
    print(f" [INFO] Encontradas {len(mac_dict)} direcciones MAC con reserva estática en UCI.")

    if args.include_leases:
        active_leases = extract_active_leases(ssh)
        for mac, info in active_leases.items():
            if mac not in mac_dict:
                mac_dict[mac] = info
                print(f" [LEASE] Agregada MAC activa de /tmp/dhcp.leases: {mac} ({info['name']} - {info['ip']})")

    for extra in args.extra_macs:
        clean_mac = extra.lower().strip()
        if re.match(r"^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", clean_mac):
            if clean_mac not in mac_dict:
                mac_dict[clean_mac] = {"name": "extra_manual", "ip": "manual"}
                print(f" [MANUAL] Agregada MAC manual: {clean_mac}")

    print("\n--- Lista Blanca Consolidada para Salida WAN ---")
    for mac, info in sorted(mac_dict.items()):
        print(f" - {mac} -> {info['name']} ({info['ip']})")

    print("\n=== PASO 3: PREPARACIÓN DE REGLA UCI FIREWALL ===")
    rule_cmds = [
        "uci set firewall.drop_unknown_mac=rule",
        "uci set firewall.drop_unknown_mac.name='Drop_Non_Whitelisted_LAN_WAN'",
        "uci set firewall.drop_unknown_mac.src='lan'",
        "uci set firewall.drop_unknown_mac.dest='wan'",
        "uci set firewall.drop_unknown_mac.proto='all'",
        "uci -q delete firewall.drop_unknown_mac.src_mac"
    ]
    for mac in sorted(mac_dict.keys()):
        rule_cmds.append(f"uci add_list firewall.drop_unknown_mac.src_mac='!{mac}'")
    rule_cmds.append("uci set firewall.drop_unknown_mac.target='DROP'")

    script_uci = "\n".join(rule_cmds)

    if args.dry_run:
        print(" [DRY-RUN] Comandos que se aplicarían en UCI:")
        print(script_uci)
        print("\n [DRY-RUN] Verificando compilación de reglas en nftables con fw4 print...")
        dry_script = f"""
        {script_uci}
        fw4 print | grep -C 3 -i 'Drop_Non_Whitelisted_LAN_WAN'
        uci revert firewall
        """
        out, err, code = run_cmd(ssh, dry_script)
        print("Salida de fw4 print:")
        print(out)
        print(" [DRY-RUN] Simulación concluida. No se realizaron cambios permanentes.")
        return

    print("\n=== PASO 4: APLICANDO Y VALIDANDO EN FIREWALL4 (NFTABLES) ===")
    apply_script = f"""
    {script_uci}
    if fw4 check; then
        uci commit firewall
        /sbin/fw4 reload
        echo "APPLY_OK"
    else
        uci revert firewall
        echo "APPLY_FAILED"
    fi
    """
    out, err, code = run_cmd(ssh, apply_script)
    if "APPLY_OK" in out:
        print(" [OK] Regla aplicada y firewall recargado con éxito.")
        print("\n=== VERIFICACIÓN EN VIVO (CHAIN forward_lan) ===")
        check_out, _, _ = run_cmd(ssh, "nft list chain inet fw4 forward_lan | grep -C 2 -i Drop_Non_Whitelisted")
        print(check_out)
    else:
        print(" [FALLO] fw4 check reportó error. Se revirtieron los cambios automáticamente.")
        print(err)


if __name__ == "__main__":
    main()

## Uso
# Simulación previa sin cambios:
# python tools/apply_mac_whitelist_firewall.py --dry-run
#
# Aplicación permanente con reservas estáticas:
# python tools/apply_mac_whitelist_firewall.py
#
# Aplicación incluyendo leases activos no guardados:
# python tools/apply_mac_whitelist_firewall.py --include-leases
#
# Reversión completa a estado original:
# python tools/apply_mac_whitelist_firewall.py --revert
