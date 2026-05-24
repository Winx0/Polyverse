"""Debug script - find BTC Up/Down 5m market via different endpoints."""
import os
import requests
from dotenv import load_dotenv
load_dotenv('.env.bot')

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

print("=" * 50)
print("TEST 1: Gamma /events?slug=btc-updown")
print("=" * 50)
try:
    resp = requests.get(f"{GAMMA}/events", params={"slug": "btc-updown-5m"}, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Response: {str(data)[:500]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 2: Gamma /events?tag=crypto&closed=false (more)")
print("=" * 50)
try:
    resp = requests.get(f"{GAMMA}/events", params={"closed": "false", "limit": 100}, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        events = resp.json()
        print(f"Total events: {len(events)}")
        for e in events:
            title = str(e.get('title', '')).lower()
            slug = str(e.get('slug', '')).lower()
            if 'btc' in title or 'btc' in slug or 'bitcoin' in title or 'crypto' in slug:
                print(f"  FOUND: {e.get('title','')} | slug={e.get('slug','')}")
                mkts = e.get('markets', [])
                if mkts:
                    print(f"    Markets: {len(mkts)}")
                    for m in mkts[:2]:
                        print(f"      - {m.get('question','')} tokens={m.get('tokens',[])}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 3: CLOB /markets (paginated, latest)")
print("=" * 50)
try:
    # Try to get latest markets by using a high cursor
    resp = requests.get(f"{CLOB}/markets", params={"next_cursor": "LTEwMA=="}, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        markets = data.get('data', []) if isinstance(data, dict) else data
        print(f"Count: {len(markets)}")
        for m in markets[:5]:
            q = m.get('question', m.get('description', ''))
            print(f"  - {q[:80]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 4: Gamma /markets?tag=live-crypto")
print("=" * 50)
try:
    for tag in ["live-crypto", "Live Crypto", "crypto-prices", "btc-5m"]:
        resp = requests.get(f"{GAMMA}/markets", params={"closed": "false", "tag": tag, "limit": 10}, timeout=10)
        if resp.status_code == 200:
            markets = resp.json()
            if markets:
                print(f"Tag '{tag}': {len(markets)} markets")
                for m in markets[:3]:
                    print(f"  - {m.get('question','')[:70]}")
                break
        else:
            print(f"Tag '{tag}': status {resp.status_code}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 5: Direct event slug fetch")
print("=" * 50)
try:
    # The known event slug pattern from web search
    resp = requests.get(f"{GAMMA}/events?slug=btc-updown-5m", timeout=15)
    print(f"Status: {resp.status_code}")
    print(f"Response: {str(resp.json())[:500] if resp.status_code == 200 else resp.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 6: Search Polymarket")  
print("=" * 50)
try:
    resp = requests.get("https://polymarket.com/api/search", params={"query": "BTC Up Down 5m"}, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Response: {str(resp.json())[:500]}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")
