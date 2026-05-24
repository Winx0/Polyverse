"""
Test single order placement on Polymarket.
Auto-tries free SOCKS5 proxies from EU to bypass geoblock.
Run: pip install pysocks && python test_order.py
"""
import os
import time
import json
from dotenv import load_dotenv
load_dotenv('.env.bot')

import requests

# --- PROXY CONFIG ---
# Try proxy from .env.bot first, then auto-try free EU proxies
PROXY = os.getenv("PROXY", "")

# Free SOCKS5 proxies from EU/allowed regions (updated from public lists)
FREE_PROXIES = [
    "socks5://5.75.211.227:1080",       # Germany (Hetzner)
    "socks5://161.97.118.197:1080",      # Germany
    "socks5://173.212.239.43:1080",      # Germany
    "socks5://152.53.144.223:1080",      # Netherlands
    "socks5://85.155.96.109:1080",       # Netherlands
    "socks5://213.121.165.12:1080",      # UK
    "socks5://89.124.79.162:1080",       # Bulgaria (EU)
    "socks5://212.48.150.38:1080",       # Poland (EU)
    "socks5://150.241.106.113:1080",     # Germany
    "socks5://167.71.42.89:1080",        # Netherlands
]

def find_working_proxy():
    """Try proxies until one works from an allowed country."""
    if PROXY:
        return PROXY

    print("[PROXY] Testing free EU proxies...")
    for proxy in FREE_PROXIES:
        try:
            r = requests.get("https://ipinfo.io/json",
                           proxies={"http": proxy, "https": proxy},
                           timeout=5)
            if r.status_code == 200:
                info = r.json()
                country = info.get("country", "")
                # Polymarket allowed: EU, UK, Canada, Singapore, etc.
                # Blocked: US, Indonesia, China
                blocked = ["US", "ID", "CN", "KP", "IR", "CU", "SY"]
                if country not in blocked:
                    print(f"[PROXY] Working! {proxy} -> {country} ({info.get('city','')})")
                    return proxy
                else:
                    print(f"[PROXY] {proxy} -> {country} (BLOCKED)")
        except Exception:
            continue
    return None

working_proxy = find_working_proxy()
if working_proxy:
    os.environ['HTTP_PROXY'] = working_proxy
    os.environ['HTTPS_PROXY'] = working_proxy
    print(f"[PROXY] Set: {working_proxy}")
else:
    print("[PROXY] No working proxy found! Order will likely fail.")

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from py_clob_client.constants import POLYGON

creds = ApiCreds(
    api_key=os.getenv('CLOB_API_KEY'),
    api_secret=os.getenv('CLOB_API_SECRET'),
    api_passphrase=os.getenv('CLOB_API_PASSPHRASE'),
)
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=POLYGON,
    key=os.getenv('PRIVATE_KEY'),
    creds=creds,
)

print("=" * 50)
print("  TEST ORDER - 1 trade $0.25")
print("=" * 50)

# Check IP
try:
    ip_info = requests.get('https://ipinfo.io/json', timeout=5).json()
    print(f"[IP] Country: {ip_info.get('country')} | IP: {ip_info.get('ip')}")
except Exception:
    pass

# Find market
current_ts = int(time.time())
current_window = (current_ts // 300) * 300
GAMMA = "https://gamma-api.polymarket.com"

market = None
for offset in [600, 300, 900]:
    slug = f"btc-updown-5m-{current_window + offset}"
    try:
        r = requests.get(f"{GAMMA}/events", params={"slug": slug}, timeout=10)
        if r.status_code == 200 and r.json():
            m = r.json()[0]['markets'][0]
            if not m.get('closed', False):
                clob_ids = m.get('clobTokenIds', [])
                if isinstance(clob_ids, str):
                    clob_ids = json.loads(clob_ids)
                if len(clob_ids) >= 2:
                    market = m
                    print(f"[OK] Market: {m['question']}")
                    break
    except Exception:
        continue

if not market:
    print("[ERROR] No market found!")
    exit(1)

clob_ids = market.get('clobTokenIds', [])
if isinstance(clob_ids, str):
    clob_ids = json.loads(clob_ids)
token_id = clob_ids[0]

print(f"\n[ORDER] BUY UP @ price=0.50, size=0.5 shares (~$0.25)...")

try:
    from py_clob_client.clob_types import OrderArgs
    order_args = OrderArgs(
        price=0.50, size=0.5, side="BUY", token_id=token_id,
    )
    result = client.create_and_post_order(order_args)
    print(f"\n[RESULT] {result}")
    print("\nSUCCESS!")
except Exception as e:
    print(f"\n[ERROR] {e}")
    if "403" in str(e) or "restricted" in str(e).lower():
        print("\n[GEOBLOCK] Kamu perlu proxy dari negara allowed.")
        print("Tambahkan di .env.bot:")
        print("  PROXY=socks5://user:pass@host:port")
        print("\nProxy gratis:")
        print("  - webshare.io (gratis 10 proxy)")
        print("  - proxy-seller.com (~$2/bulan)")
        print("  - proxyscrape.com/free-proxy-list (SOCKS5, country=DE/NL/UK)")
