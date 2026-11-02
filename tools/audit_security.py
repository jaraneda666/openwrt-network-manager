import sys
from openwrt_client import OpenWrtClient

client = OpenWrtClient(host="192.168.1.1")
try:
    client.connect()
    print("=== CONNECTED TO ROUTER ===")
    
    # 1. Listening ports (netstat / ss)
    code, out, err = client.exec_command("netstat -tulnp 2>/dev/null || ss -tulnp 2>/dev/null", check_safety=False)
    print("\n--- LISTENING PORTS ---")
    print(out)
    
    # 2. Dropbear config
    code, out, err = client.exec_command("uci show dropbear", check_safety=False)
    print("\n--- DROPBEAR CONFIG ---")
    print(out)
    
    # 3. uhttpd config
    code, out, err = client.exec_command("uci show uhttpd", check_safety=False)
    print("\n--- UHTTPD CONFIG ---")
    print(out)
    
    # 4. upnpd config
    code, out, err = client.exec_command("uci show upnpd 2>/dev/null", check_safety=False)
    print("\n--- UPNPD CONFIG ---")
    print(out)
    
    # 5. samba4 config
    code, out, err = client.exec_command("uci show samba4 2>/dev/null", check_safety=False)
    print("\n--- SAMBA4 CONFIG ---")
    print(out)
    
    # 6. openvpn config
    code, out, err = client.exec_command("uci show openvpn 2>/dev/null", check_safety=False)
    print("\n--- OPENVPN CONFIG ---")
    print(out)
    
    # 7. Firewall zones and forwards
    code, out, err = client.exec_command("uci show firewall", check_safety=False)
    print("\n--- FIREWALL CONFIG ---")
    print(out)
    
    # 8. Password / Shadow check (empty passwords / root)
    code, out, err = client.exec_command("cat /etc/shadow | grep -E '^root:|^ubnt:'", check_safety=False)
    print("\n--- SHADOW CHECK (hashes masked or present) ---")
    for line in out.splitlines():
        parts = line.split(":")
        print(f"User: {parts[0]}, HasPassword: {bool(parts[1] and parts[1] != '*' and parts[1] != '!')}")
        
    # 9. Crontabs
    code, out, err = client.exec_command("cat /etc/crontabs/root 2>/dev/null", check_safety=False)
    print("\n--- CRONTAB ---")
    print(out)
    
    # 10. SSH authorized_keys
    code, out, err = client.exec_command("wc -l /etc/dropbear/authorized_keys 2>/dev/null", check_safety=False)
    print("\n--- AUTHORIZED KEYS COUNT ---")
    print(out)
    
except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
