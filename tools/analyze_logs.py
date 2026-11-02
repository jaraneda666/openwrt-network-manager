import sys
import re
from pathlib import Path
from collections import Counter

sys.path.append(str(Path(__file__).parent))
from openwrt_client import OpenWrtClient

def main():
    client = OpenWrtClient()
    client.connect()
    _, out, _ = client.exec_command("logread | grep 'reject wan in:'", check_safety=False)

    lines = [l for l in out.strip().splitlines() if "reject wan in:" in l]
    dpts = Counter()
    protos = Counter()
    srcs = Counter()

    for line in lines:
        m_dpt = re.search(r'DPT=(\d+)', line)
        m_proto = re.search(r'PROTO=(\w+)', line)
        m_src = re.search(r'SRC=([\d\.]+)', line)
        if m_dpt:
            dpts[m_dpt.group(1)] += 1
        if m_proto:
            protos[m_proto.group(1)] += 1
        if m_src:
            srcs[m_src.group(1)] += 1

    print(f"Total registros muestreados: {len(lines)}")
    print("Distribución de Puertos Destino (DPT):")
    for port, count in dpts.most_common():
        pct = (count / len(lines)) * 100
        print(f"  - Puerto {port}: {count} eventos ({pct:.1f}%)")

    print("\nProtocolos:")
    for proto, count in protos.most_common():
        print(f"  - {proto}: {count} eventos")

    print("\nTop 5 IPs de origen más recurrentes:")
    for ip, count in srcs.most_common(5):
        print(f"  - {ip}: {count} eventos")

if __name__ == "__main__":
    main()
