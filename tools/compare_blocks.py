import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.100', 22, os.environ.get("ADMIN_USER", "admin"), os.environ.get("ADMIN_PASS", ""))

stdin, stdout, stderr = client.exec_command("cat /etc/nginx/sites-enabled/server.ReverseProxy.conf")
content = stdout.read().decode('utf-8', errors='replace')
for b in content.split("server {"):
    if "portainer.admin.synology.me" in b:
        print("=== PORTAINER ===")
        print("server {" + b)
    if "router.admin.synology.me" in b:
        print("=== ROUTER ===")
        print("server {" + b)

client.close()
