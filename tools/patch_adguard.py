import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from openwrt_client import OpenWrtClient

def main():
    client = OpenWrtClient()
    client.connect()

    # Read current yaml
    code, content, err = client.exec_command("cat /etc/adguardhome.yaml", check_safety=False)
    if code != 0:
        print(f"Error reading yaml: {err}")
        return 1

    # Replace local_ptr_upstreams
    old_ptr = "  local_ptr_upstreams: []"
    new_ptr = "  local_ptr_upstreams:\n    - 127.0.0.1:54"

    old_fb = "  fallback_dns: []"
    new_fb = "  fallback_dns:\n    - 9.9.9.9\n    - 1.1.1.1"

    if old_ptr not in content:
        print("old_ptr not found in file")
        return 1
    if old_fb not in content:
        print("old_fb not found in file")
        return 1

    content = content.replace(old_ptr, new_ptr, 1)
    content = content.replace(old_fb, new_fb, 1)

    # Use stdin to write back safely
    stdin, stdout, stderr = client.ssh.exec_command("cat > /etc/adguardhome.yaml")
    stdin.write(content)
    stdin.flush()
    stdin.channel.shutdown_write()
    err_write = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f"Error writing /etc/adguardhome.yaml: {err_write}")
        return 1

    print("adguardhome.yaml successfully updated via SFTP.")
    # Restart service
    code_r, out_r, err_r = client.exec_command("/etc/init.d/adguardhome restart", check_safety=False)
    print(f"Restart code: {code_r}, output: {out_r.strip()} {err_r.strip()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
