"""
Test single order - direct, no proxy logic.
Uses VPN connection directly.
Run: python test_order.py
"""
import os
import time
import json
from dotenv import load_dotenv
load_dotenv('.env.bot')

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs
from py_clob_client.constants import POLYGON

# Setup client
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
print("  TEST ORDER - direct VPN (no proxy)")
print("=" * 50)

# Check IP
try:
    ip_info = requests.get('https://ipinfo.io/json', timeout=5).json()
    print(f"[IP] Country: {ip_info.get('country')} | City: {ip_info.get('city')} | IP: {ip_info.get('ip')}")
except Exception as e:
    print(f"[IP] Check failed: {e}")

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
print(f"[ORDER] Token: {token_id[:30]}...")

try:
    order_args = OrderArgs(
        price=0.50, size=0.5, side="BUY", token_id=token_id,
    )
    result = client.create_and_post_order(order_args)
    print(f"\n[RESULT] {result}")
    print("\nSUCCESS! Order placed!")
except Exception as e:
    print(f"\n[ERROR] {e}")
    if "403" in str(e) or "restricted" in str(e).lower():
        print("\n[GEOBLOCK] VPN tidak work untuk trading.")
        print("Polymarket detect IP sebagai restricted.")
        print("Coba ganti server VPN ke negara lain (NL/UK/SG/JP)")
