import requests
import time
import socket
import ssl
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============== ACTIVE SOURCES (2026) ==============
SOURCES = [
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vless_configs.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/vless.txt",
    "https://raw.githubusercontent.com/hamedcode/port-based-v2ray-configs/main/sub/vless.txt",
]

EXCLUDE_COUNTRIES = {"🇮🇷", "🇷🇺", "🇨🇳", "🇹🇷", "IR", "RU", "CN", "TR"}
TOP_N = 150
MAX_ACCEPTABLE_LATENCY = 2500  # ms

def should_exclude(config):
    try:
        remark = config.split('#')[-1].upper()
        return any(c in remark for c in EXCLUDE_COUNTRIES)
    except:
        return False

def extract_host_and_port(vless_url):
    try:
        url_part = vless_url.split('#')[0]
        if url_part.startswith('vless://'):
            without_scheme = url_part[8:]
            if '@' in without_scheme:
                hostport_part = without_scheme.split('@')[1].split('?')[0].split('/')[0]
                if ':' in hostport_part:
                    host, port = hostport_part.rsplit(':', 1)
                    return host.strip(), int(port)
    except:
        pass
    return None, None

def test_node(cfg):
    """Patient TLS test - very thorough"""
    host, port = extract_host_and_port(cfg)
    if not host or not port:
        return None, 9999

    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(6.0)

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        secure_sock = context.wrap_socket(sock, server_hostname=host)
        secure_sock.settimeout(8.0)
        secure_sock.connect((host, port))

        secure_sock.settimeout(3.0)
        try:
            secure_sock.recv(512)
        except:
            pass

        secure_sock.close()

        latency = (time.time() - start_time) * 1000
        return cfg, round(latency, 1)

    except Exception:
        return None, 9999

def main():
    print("🔄 Fetching latest VLESS configs...")
    configs = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VLESS-Generator/6.0)"}

    for url in SOURCES:
        try:
            resp = requests.get(url, timeout=25, headers=headers)
            if resp.status_code == 200:
                lines = [line.strip() for line in resp.text.splitlines() if line.strip().startswith('vless://')]
                configs.extend(lines)
                print(f"   → Loaded {len(lines)} nodes from {url.split('/')[-1]}")
        except:
            print(f"   → Failed to fetch one source")

    configs = list(set(configs))
    total = len(configs)
    print(f"✅ Total unique configs: {total}")

    print("⚡ Testing all nodes (this may take 3–8 minutes)...")
    active = []
    with ThreadPoolExecutor(max_workers=35) as executor:
        futures = [executor.submit(test_node, c) for c in configs]
        for future in as_completed(futures):
            cfg, latency = future.result()
            if cfg and latency < MAX_ACCEPTABLE_LATENCY:
                active.append((cfg, latency))

    active.sort(key=lambda x: x[1])

    final_nodes = []
    for cfg, latency in active[:TOP_N]:
        try:
            base, remark = cfg.split('#', 1)
            new_remark = f"{remark.strip()} | {latency}ms"
            final_nodes.append(f"{base}#{new_remark}")
        except:
            final_nodes.append(cfg)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    header = f"""# profile-title: 🚀 Active VLESS Subscription - Auto Updated
# profile-update-interval: 6
# Generated: {now}
# Total tested: {total}
# Active nodes: {len(active)}
# Only live nodes (full TLS test)
# Sorted by: Lowest latency first
"""

    content = header + "\n".join(final_nodes)

    with open("subscription.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ subscription.txt generated with {len(final_nodes)} active nodes")

if __name__ == "__main__":
    main()
