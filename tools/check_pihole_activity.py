import paramiko
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.100', 22, os.environ.get("ADMIN_USER", "admin"), os.environ.get("ADMIN_PASS", ""), timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f'echo "$ADMIN_PASS" | sudo -S {cmd}')
    return stdout.read().decode('utf-8', errors='replace').strip()

DOCKER = '/var/packages/ContainerManager/target/usr/bin/docker'

print('=== PIHOLE CHRONOMETER ===')
print(run(f'{DOCKER} exec Pi-Hole pihole -c -e'))

print('\n=== LAST 15 LOG LINES (FTL.log) ===')
print(run('tail -n 15 /volume1/docker/pihole/pihole/FTL.log'))

print('\n=== PIHOLE QUERY TEST (dig @192.168.1.100 google.com) ===')
print(run(f'{DOCKER} exec Pi-Hole dig @127.0.0.1 google.com +short'))

print('\n=== PIHOLE LOCAL QUERY TEST (dig @192.168.1.100 router.lan) ===')
print(run(f'{DOCKER} exec Pi-Hole dig @127.0.0.1 router.lan +short'))

client.close()
