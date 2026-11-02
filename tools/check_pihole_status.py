import paramiko
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.1.100', 22, os.environ.get("ADMIN_USER", "admin"), os.environ.get("ADMIN_PASS", ""), timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f'echo "$ADMIN_PASS" | sudo -S {cmd}')
    return stdout.read().decode('utf-8', errors='replace').strip()

DOCKER = '/var/packages/ContainerManager/target/usr/bin/docker'

print('=== PIHOLE STATUS ===')
print(run(f'{DOCKER} exec Pi-Hole pihole status'))

print('\n=== PIHOLE FTL VERSION ===')
print(run(f'{DOCKER} exec Pi-Hole pihole -v'))

print('\n=== PIHOLE.TOML ACTIVE SETTINGS ===')
toml_raw = run('cat /volume1/docker/pihole/pihole/pihole.toml')
for line in toml_raw.splitlines():
    line_s = line.strip()
    if line_s and not line_s.startswith('#'):
        print(line)

print('\n=== PIHOLE DOCKER ENV VARS ===')
print(run(f"{DOCKER} inspect Pi-Hole --format '{{{{json .Config.Env}}}}'"))

client.close()
