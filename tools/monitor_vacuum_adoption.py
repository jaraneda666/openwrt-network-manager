import paramiko
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

k = r"C:\Users\Developer\.ssh\id_ed25519"
ROUTER_IP = "192.168.1.1"
AP1_IP = "192.168.1.253"
AP2_IP = "192.168.1.254"
VACUUM_MAC = "cc:4d:75:75:14:7d"
VACUUM_IP = "192.168.2.186"

def get_ssh(ip):
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(ip, username="root", key_filename=k, timeout=5)
    return s

print("=== INICIANDO MONITOR EN VIVO DE ADOPCIÓN DE ASPIRADORA ===")
router = get_ssh(ROUTER_IP)
ap1 = get_ssh(AP1_IP)
ap2 = get_ssh(AP2_IP)

for i in range(1, 7):
    print(f"\n--- SONDEO #{i} ({time.strftime('%H:%M:%S')}) ---")
    
    # 1. Asociaciones Wi-Fi en APs
    _, out1, _ = ap1.exec_command(f"iwinfo phy1-ap2 assoclist | grep -i '{VACUUM_MAC}'")
    assoc1 = out1.read().decode('utf-8').strip()
    
    _, out2, _ = ap2.exec_command(f"iwinfo phy1-ap2 assoclist | grep -i '{VACUUM_MAC}'")
    assoc2 = out2.read().decode('utf-8').strip()
    
    if assoc1:
        print(f"  [Wi-Fi AP1]: Conectada a AP1 (Salón/Pasillo) -> {assoc1.splitlines()[0]}")
    elif assoc2:
        print(f"  [Wi-Fi AP2]: Conectada a AP2 (Habitaciones) -> {assoc2.splitlines()[0]}")
    else:
        print("  [Wi-Fi]: Esperando asociación inalámbrica a SSID 'Casa_IoT'...")

    # 2. Eventos DHCP recientes en Router
    _, out_dhcp, _ = router.exec_command(f"logread | grep -i '{VACUUM_MAC}' | tail -n 4")
    logs = out_dhcp.read().decode('utf-8').strip()
    if logs:
        print("  [Logs DHCP / Kernel]:")
        for line in logs.splitlines():
            print(f"    {line}")

    # 3. Conexiones activas en Conntrack
    _, out_ct, _ = router.exec_command(f"grep '{VACUUM_IP}' /proc/net/nf_conntrack | head -n 4")
    ct = out_ct.read().decode('utf-8').strip()
    if ct:
        print("  [Conexiones WAN / Nube]:")
        for line in ct.splitlines():
            print(f"    {line}")

    # 4. Ping de verificación si ya tiene IP
    _, out_ping, _ = router.exec_command(f"ping -c 1 -W 1 {VACUUM_IP} > /dev/null && echo OK || echo NO_REPLY")
    ping_res = out_ping.read().decode('utf-8').strip()
    print(f"  [Ping a {VACUUM_IP}]: {ping_res}")
    
    time.sleep(5)

router.close()
ap1.close()
ap2.close()
print("\n=== FIN DE LA SESIÓN DE MONITOREO INICIAL ===")
