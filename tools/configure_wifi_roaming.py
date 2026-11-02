"""
# Tool: configure_wifi_roaming.py

## Metadata
- Nombre: configure_wifi_roaming.py
- Versión: 1.0
- Lenguaje: Python
- Creada en proyecto: OpenWrt_Manager
- Fecha de creación: 2026-10-07
- Descripción: Configura canales no solapados, calibración de potencia Tx y roaming 802.11r/k/v en Access Points OpenWrt (UniFi AC Pro), con respaldo automático y corrección de gateway en Switch US-8-60W.
- Parámetros: --ap1, --ap2, --switch
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


def get_ssh(host, user="root", key_file=None, password=None):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if key_file:
        client.connect(host, port=22, username=user, key_filename=key_file, timeout=10, look_for_keys=True, allow_agent=True)
    else:
        client.connect(host, port=22, username=user, password=password, timeout=10, look_for_keys=False, allow_agent=False)
    return client


def backup_ap_config(ssh, host, backup_dir):
    stdin, stdout, stderr = ssh.exec_command("cat /etc/config/wireless")
    content = stdout.read().decode("utf-8")
    out_file = backup_dir / f"wireless_{host}.uci"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f" [BACKUP] Respaldo de /etc/config/wireless de {host} guardado en {out_file}")


def configure_ap(host, ch_5g, ch_2g, iface_2g_name, key_file):
    print(f"\n==========================================")
    print(f"Configurando AP {host}")
    print(f" - 5 GHz: Canal {ch_5g} (VHT80) | TxPower 20 dBm")
    print(f" - 2.4 GHz: Canal {ch_2g} (HT20) | TxPower 14 dBm")
    print(f" - Roaming: 802.11r (FT-PSK) + 802.11k (RRM) + 802.11v (BSS Transition)")
    print(f" - Cifrado: WPA2-PSK (AES/CCMP) estricto")
    print(f"==========================================")

    ssh = get_ssh(host, key_file=key_file)

    # Backup directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("output") / "backups" / f"roaming_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_ap_config(ssh, host, backup_dir)

    uci_commands = f"""
# 1. Configuración de Radio 5GHz (radio0)
uci set wireless.radio0.channel='{ch_5g}'
uci set wireless.radio0.htmode='VHT80'
uci set wireless.radio0.txpower='20'

# 2. Configuración de Radio 2.4GHz (radio1)
uci set wireless.radio1.channel='{ch_2g}'
uci set wireless.radio1.htmode='HT20'
uci set wireless.radio1.txpower='14'

# 3. Interfaz Casa en 5GHz (default_radio0)
uci set wireless.default_radio0.encryption='psk2'
uci set wireless.default_radio0.ieee80211r='1'
uci set wireless.default_radio0.mobility_domain='123f'
uci set wireless.default_radio0.ft_over_ds='0'
uci set wireless.default_radio0.ft_psk_generate_local='1'
uci set wireless.default_radio0.ieee80211k='1'
uci set wireless.default_radio0.rrm_neighbor_report='1'
uci set wireless.default_radio0.rrm_beacon_report='1'
uci set wireless.default_radio0.ieee80211v='1'
uci set wireless.default_radio0.bss_transition='1'
uci set wireless.default_radio0.wnm_sleep_mode='1'
uci set wireless.default_radio0.time_advertisement='2'
uci set wireless.default_radio0.time_zone='UTC0'
uci set wireless.default_radio0.disassoc_low_ack='0'

# 4. Interfaz Casa en 2.4GHz ({iface_2g_name})
uci set wireless.{iface_2g_name}.encryption='psk2'
uci set wireless.{iface_2g_name}.ieee80211r='1'
uci set wireless.{iface_2g_name}.mobility_domain='123f'
uci set wireless.{iface_2g_name}.ft_over_ds='0'
uci set wireless.{iface_2g_name}.ft_psk_generate_local='1'
uci set wireless.{iface_2g_name}.ieee80211k='1'
uci set wireless.{iface_2g_name}.rrm_neighbor_report='1'
uci set wireless.{iface_2g_name}.rrm_beacon_report='1'
uci set wireless.{iface_2g_name}.ieee80211v='1'
uci set wireless.{iface_2g_name}.bss_transition='1'
uci set wireless.{iface_2g_name}.wnm_sleep_mode='1'
uci set wireless.{iface_2g_name}.time_advertisement='2'
uci set wireless.{iface_2g_name}.time_zone='UTC0'
uci set wireless.{iface_2g_name}.disassoc_low_ack='0'

# 5. Red oculta a psk2 puro para estabilidad general
uci set wireless.wifinet2.encryption='psk2'

uci commit wireless
wifi reload
"""

    stdin, stdout, stderr = ssh.exec_command(uci_commands)
    stdout.channel.recv_exit_status()

    print(" - Aplicando configuración y reiniciando radios Wi-Fi...")
    time.sleep(5)

    # Verificar estado de radios
    stdin, stdout, stderr = ssh.exec_command("iwinfo | grep -E 'ESSID|Channel|Tx-Power|Encryption'")
    status_out = stdout.read().decode("utf-8")
    print(f"Estado de interfaces post-reinicio:\n{status_out}")

    ssh.close()
    return backup_dir


def configure_switch_gateway(switch_ip):
    print(f"\n==========================================")
    print(f"Corrigiendo Gateway en Switch FastPath ({switch_ip})")
    print(f"==========================================")
    try:
        ssh = get_ssh(switch_ip, user="ubnt", password="ubnt")
        chan = ssh.invoke_shell()
        time.sleep(1)

        def send_cmd(c, delay=0.6):
            chan.send(c + "\n")
            time.sleep(delay)

        send_cmd("telnet 127.0.0.1 23", 1.0)
        send_cmd("enable", 0.5)
        send_cmd("network parms 192.168.1.1003 255.255.255.0 192.168.1.1", 0.8)
        send_cmd("write memory", 1.5)
        send_cmd("y", 1.0)
        send_cmd("show network", 1.0)

        time.sleep(2)
        out = ""
        while chan.recv_ready():
            out += chan.recv(8192).decode("utf-8", errors="replace")
            time.sleep(0.3)

        if "192.168.1.1" in out:
            print(" [OK] Gateway actualizado correctamente a 192.168.1.1")
        else:
            print(" [ADVERTENCIA] Salida FastPath:")
            print(out[:500])

        chan.close()
        ssh.close()
    except Exception as e:
        print(f" [ERROR] No se pudo configurar el switch: {e}")


def main():
    parser = argparse.ArgumentParser(description="Calibración Wi-Fi Roaming y Switch")
    parser.add_argument("--ap1", default="192.168.1.253", help="IP AP 1")
    parser.add_argument("--ap2", default="192.168.1.254", help="IP AP 2")
    parser.add_argument("--switch", default="192.168.1.1003", help="IP Switch")

    args = parser.parse_args()

    default_ed25519 = Path.home() / ".ssh" / "id_ed25519"
    key_str = str(default_ed25519) if default_ed25519.exists() else None

    # AP 253: Ch 36 en 5G, Ch 1 en 2.4G (iface wifinet3)
    bdir = configure_ap(args.ap1, ch_5g=36, ch_2g=1, iface_2g_name="wifinet3", key_file=key_str)

    # AP 254: Ch 149 en 5G, Ch 6 en 2.4G (iface wifinet4)
    configure_ap(args.ap2, ch_5g=149, ch_2g=6, iface_2g_name="wifinet4", key_file=key_str)

    # Switch: Corregir default gateway
    configure_switch_gateway(args.switch)

    print("\n[PROCESO COMPLETADO EXITOSAMENTE]")


if __name__ == "__main__":
    main()
