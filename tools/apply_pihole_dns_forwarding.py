import paramiko
import sys
import datetime
import time

sys.stdout.reconfigure(encoding='utf-8')

NAS_HOST = "192.168.1.100"
NAS_USER = os.environ.get("ADMIN_USER", "admin")
NAS_PASS = os.environ.get("ADMIN_PASS", "")
DOCKER = "/var/packages/ContainerManager/target/usr/bin/docker"
TOML_PATH = "/volume1/docker/pihole/pihole/pihole.toml"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(NAS_HOST, 22, NAS_USER, NAS_PASS, timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f'echo {NAS_PASS} | sudo -S {cmd}')
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
bak_path = f"{TOML_PATH}.bak_{timestamp}"

print(f"1. Creando respaldo preventivo en Synology NAS: {bak_path}")
out, err = run(f"cp {TOML_PATH} {bak_path}")
print("Respaldo creado:", out if out else "OK")

print("\n2. Leyendo contenido de pihole.toml...")
out, err = run(f"cat {TOML_PATH}")
content = out

old_rev = 'revServers = [\n    "true,192.168.1.0/24,192.168.1.100,synology.me"\n  ]'
new_rev = 'revServers = [\n    "true,192.168.1.0/24,192.168.1.1,lan"\n  ]'

old_up = 'upstreams = [\n    "8.8.8.8",\n    "8.8.4.4"\n  ]'
new_up = 'upstreams = [\n    "9.9.9.9",\n    "1.1.1.1",\n    "8.8.8.8"\n  ]'

if old_rev in content:
    content = content.replace(old_rev, new_rev)
    print("Reemplazado revServers exitosamente.")
else:
    print("AVISO: No se encontró la cadena exacta de old_rev, buscando alternativa...")
    # fallback line replace
    lines = content.splitlines()
    new_lines = []
    in_rev = False
    for line in lines:
        if 'revServers =' in line:
            new_lines.append('  revServers = [')
            new_lines.append('    "true,192.168.1.0/24,192.168.1.1,lan"')
            new_lines.append('  ] ### CHANGED, default = []')
            in_rev = True
        elif in_rev:
            if ']' in line:
                in_rev = False
        else:
            new_lines.append(line)
    content = "\n".join(new_lines)

if old_up in content:
    content = content.replace(old_up, new_up)
    print("Reemplazado upstreams con Quad9, Cloudflare y Google.")

# Escribir el nuevo archivo via stdin
tmp_file = f"/tmp/pihole.toml.{timestamp}"
stdin_pipe, stdout_pipe, stderr_pipe = client.exec_command(f"cat > {tmp_file}")
stdin_pipe.write(content)
stdin_pipe.channel.shutdown_write()
stdout_pipe.channel.recv_exit_status()

print("\n3. Aplicando nuevo pihole.toml...")
run(f"cp {tmp_file} {TOML_PATH}")
run(f"rm {tmp_file}")

print("\n4. Reiniciando contenedor Pi-Hole...")
out, err = run(f"{DOCKER} restart Pi-Hole")
print("Docker restart:", out)

print("\n5. Esperando 5 segundos a que FTL inicialice...")
time.sleep(5)

print("\n6. Verificando resolucion DNS en Pi-Hole:")
out_local, _ = run(f"{DOCKER} exec Pi-Hole dig @127.0.0.1 router.lan +short")
print(f"  router.lan -> {out_local}")

out_nas, _ = run(f"{DOCKER} exec Pi-Hole dig @127.0.0.1 nas.lan +short")
print(f"  nas.lan -> {out_nas}")

out_ptr, _ = run(f"{DOCKER} exec Pi-Hole dig @127.0.0.1 -x 192.168.1.1 +short")
print(f"  PTR 192.168.1.1 -> {out_ptr}")

out_ext, _ = run(f"{DOCKER} exec Pi-Hole dig @127.0.0.1 cloudflare.com +short")
print(f"  cloudflare.com -> {out_ext}")

client.close()
