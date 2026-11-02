import paramiko
import json

def audit_openwrt():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('192.168.1.1', 22, 'root', os.environ.get("SYNO_PASS", ""), timeout=5)
    print("================ OPENWRT SECURITY AUDIT ================")
    
    cmds = [
        ("Dispositivos en Red (ARP / Leases)", "cat /tmp/dhcp.leases; cat /proc/net/arp"),
        ("Reglas de Port Forwarding / NAT WAN", "uci show firewall | grep -E 'redirect|forwarding'"),
        ("UPnP / MiniUPnPd Estado y Mapeos Activos", "uci show upnpd; iptables -t nat -L MINIUPNPD -n -v 2>/dev/null || nft list chain inet fw4 dstnat 2>/dev/null | grep -i upnp"),
        ("Configuracion WiFi (Seguridad / Cifrado / WPS)", "uci show wireless | grep -E 'encryption|wps|key|isolate'"),
        ("Configuracion SSH Dropbear", "uci show dropbear"),
        ("Configuracion uhttpd (LuCI)", "uci show uhttpd"),
        ("Aislamiento VLANs (Guest / IoT / LAN)", "uci show firewall | grep -E 'zone|forwarding'"),
        ("Version de OpenWrt y Kernel", "cat /etc/openwrt_release; uname -a")
    ]
    for title, cmd in cmds:
        print(f"\n--- {title} ---")
        _, out, _ = ssh.exec_command(cmd)
        print(out.read().decode('utf-8', errors='replace').strip())
        
    ssh.close()

def audit_synology():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('192.168.1.100', 22, os.environ.get("ADMIN_USER", "admin"), os.environ.get("SYNO_PASS", ""), timeout=5)
    print("\n================ SYNOLOGY SECURITY AUDIT ================")
    
    cmds = [
        ("Puertos Abiertos en Synology", "echo "" | sudo -S netstat -tulpn | grep LISTEN"),
        ("Firewall y AutoBlock Synology", "synogetkeyvalue /etc/synoinfo.conf run_firewall 2>/dev/null; synogetkeyvalue /etc/synoinfo.conf autoblock_enable 2>/dev/null"),
        ("Reglas de Reverse Proxy sin ACL", "grep -E 'server_name|proxy_pass' /etc/nginx/sites-enabled/server.ReverseProxy.conf | head -n 30"),
        ("Contenedores Privilegiados o con root", "echo "" | sudo -S /var/packages/ContainerManager/target/usr/bin/docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'")
    ]
    for title, cmd in cmds:
        print(f"\n--- {title} ---")
        _, out, _ = ssh.exec_command(cmd)
        print(out.read().decode('utf-8', errors='replace').strip())
        
    ssh.close()

if __name__ == "__main__":
    audit_openwrt()
    audit_synology()
