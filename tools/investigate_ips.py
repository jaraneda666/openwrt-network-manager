import subprocess
import json
from collections import defaultdict, Counter

targets = [
    '192.168.1.11', '192.168.1.15', '192.168.1.17', '192.168.1.19',
    '192.168.1.1001', '192.168.1.1002', '192.168.2.116', '192.168.2.153',
    '192.168.2.188'
]

pattern = "|".join(targets)
cmd = f"grep -E '{pattern}' /var/lib/adguardhome/data/querylog.json | tail -n 3000"

res = subprocess.run(
    ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', 'root@192.168.1.1', cmd],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='ignore'
)

queries_by_ip = defaultdict(Counter)
for line in res.stdout.strip().split('\n'):
    if not line:
        continue
    try:
        obj = json.loads(line)
        ip = obj.get('IP')
        qh = obj.get('QH')
        if ip in targets and qh:
            queries_by_ip[ip][qh] += 1
    except Exception:
        pass

for ip in targets:
    counts = queries_by_ip[ip].most_common(6)
    print(f"=== IP: {ip} ===")
    if counts:
        for domain, count in counts:
            print(f"   {domain}: {count}")
    else:
        print("   (Sin actividad DNS en querylog reciente)")
