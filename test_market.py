"""Debug script - find BTC Up/Down 5m market."""
import os
import requests
from dotenv import load_dotenv
load_dotenv('.env.bot')

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
print("TEST 1: Gamma API - search for BTC crypto markets")
print("=" * 50)
try:
    url = "https://gamma-api.polymarket.com/markets"
    params = {"closed": "false", "tag": "crypto", "limit": 50}
    resp = requests.get(url, params=params, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        markets = resp.json()
        print(f"Count: {len(markets)}")
        for m in markets[:10]:
            q = m.get('question', '')
            print(f"  - {q[:80]}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 2: Gamma API - search slug 'btc'")
print("=" * 50)
try:
    url = "https://gamma-api.polymarket.com/markets"
    params = {"closed": "false", "slug_contains": "btc", "limit": 20}
    resp = requests.get(url, params=params, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        markets = resp.json()
        print(f"Count: {len(markets)}")
        for m in markets[:10]:
            q = m.get('question', '')
            s = m.get('slug', '')
            print(f"  - {q[:60]} | slug={s[:30]}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 3: Gamma events - crypto")
print("=" * 50)
try:
    url = "https://gamma-api.polymarket.com/events"
    params = {"closed": "false", "tag": "crypto", "limit": 20}
    resp = requests.get(url, params=params, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        events = resp.json()
        print(f"Count: {len(events)}")
        for e in events[:10]:
            title = e.get('title', e.get('question', ''))
            slug = e.get('slug', '')
            markets = e.get('markets', [])
            print(f"  - {title[:60]} | markets={len(markets)} | slug={slug[:30]}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 4: CLOB /simplified-markets last page")
print("=" * 50)
try:
    url = "https://clob.polymarket.com/simplified-markets"
    params = {"limit": 10, "order": "id", "ascending": "false"}
    resp = requests.get(url, params=params, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        markets = data.get('data', [])
        print(f"Count: {len(markets)}")
        for m in markets[:10]:
            q = m.get('question', '')
            cid = m.get('condition_id', '')[:20]
            print(f"  - {q[:70]} | id={cid}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")
