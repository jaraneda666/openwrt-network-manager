import paramiko
import sys
import datetime

sys.stdout.reconfigure(encoding='utf-8')

k = r"C:\Users\Developer\.ssh\id_ed25519"
ROUTER_IP = "192.168.1.1"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(ROUTER_IP, username="root", key_filename=k, timeout=10)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
print(f"1. Creando respaldo de /etc/avahi/avahi-daemon.conf...")
run(f"cp /etc/avahi/avahi-daemon.conf /etc/avahi/avahi-daemon.conf.bak_{timestamp}")

print("2. Leyendo y configurando avahi-daemon.conf...")
conf, _ = run("cat /etc/avahi/avahi-daemon.conf")

# Reemplazar enable-reflector=no por yes
if "enable-reflector=no" in conf:
    conf = conf.replace("enable-reflector=no", "enable-reflector=yes")
    print("  -> enable-reflector=yes configurado.")
elif "enable-reflector=yes" not in conf:
    conf = conf.replace("[reflector]", "[reflector]\nenable-reflector=yes")

# Configurar allow-interfaces=br-lan.50,br-lan.60 en [server] para evitar fugas a WAN o Guest
if "allow-interfaces=" not in conf:
    conf = conf.replace("[server]", "[server]\nallow-interfaces=br-lan.50,br-lan.60")
    print("  -> allow-interfaces=br-lan.50,br-lan.60 configurado.")

# Guardar nuevo archivo
stdin_p, stdout_p, _ = ssh.exec_command("cat > /etc/avahi/avahi-daemon.conf")
stdin_p.write(conf)
stdin_p.channel.shutdown_write()
stdout_p.channel.recv_exit_status()

print("\n3. Configurando regla de cortafuegos para mDNS (UDP 5353) en zona IOT...")
run("uci set firewall.Allow_mDNS_IOT=rule")
run("uci set firewall.Allow_mDNS_IOT.name='Allow-mDNS-IOT'")
run("uci set firewall.Allow_mDNS_IOT.src='IOT_to_WAN'")
run("uci set firewall.Allow_mDNS_IOT.proto='udp'")
run("uci set firewall.Allow_mDNS_IOT.dest_port='5353'")
run("uci set firewall.Allow_mDNS_IOT.target='ACCEPT'")
run("uci commit firewall")

print("\n4. Recargando firewall y reiniciando avahi-daemon...")
run("/etc/init.d/firewall reload")
run("/etc/init.d/avahi-daemon restart")

print("\n5. Verificando estado de avahi-daemon...")
out_st, _ = run("/etc/init.d/avahi-daemon status")
print(f"  Estado Avahi: {out_st}")

out_ps, _ = run("ps | grep avahi-daemon | grep -v grep")
print(f"  Proceso: {out_ps}")

print("\n6. Verificando regla nftables:")
out_nft, _ = run("nft list chain inet fw4 input_IOT_to_WAN | grep 5353")
print(f"  Regla en nftables: {out_nft}")

ssh.close()
