"""Debug script - find BTC Up/Down 5m via sampling/RTDS endpoints."""
import os
import requests
from dotenv import load_dotenv
load_dotenv('.env.bot')

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

print("=" * 50)
print("TEST 1: CLOB /sampling-simplified-markets")
print("=" * 50)
try:
    resp = requests.get(f"{CLOB}/sampling-simplified-markets", timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, dict):
            print(f"Keys: {list(data.keys())}")
            markets = data.get('data', [])
        else:
            markets = data
        print(f"Count: {len(markets)}")
        for m in markets[:5]:
            print(f"  - {m.get('question','')[:70]} | tokens={len(m.get('tokens',[]))}")
        # Search BTC
        for m in markets:
            q = str(m.get('question','')).lower()
            if 'btc' in q or 'bitcoin' in q:
                print(f"\n  BTC FOUND: {m.get('question','')}")
                print(f"    Tokens: {m.get('tokens',[])[:2]}")
                print(f"    ID: {m.get('condition_id','')[:40]}")
                break
    else:
        print(f"Error: {resp.text[:300]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 2: CLOB /sampling-markets")
print("=" * 50)
try:
    resp = requests.get(f"{CLOB}/sampling-markets", timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, dict):
            print(f"Keys: {list(data.keys())}")
            markets = data.get('data', data.get('markets', []))
        else:
            markets = data
        print(f"Count: {len(markets)}")
        for m in markets[:5]:
            if isinstance(m, dict):
                print(f"  - {m.get('question','')[:70]}")
    else:
        print(f"Error: {resp.text[:300]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 3: CLOB /live-activity/markets")
print("=" * 50)
try:
    resp = requests.get(f"{CLOB}/live-activity/markets", timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Type: {type(data)}")
        print(f"Response: {str(data)[:500]}")
    else:
        print(f"Error: {resp.text[:300]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 4: Gamma /markets?type=sampling")
print("=" * 50)
try:
    for param_set in [
        {"type": "sampling", "limit": 10},
        {"market_type": "sampling", "limit": 10},
        {"category": "crypto-prices", "limit": 10},
    ]:
        resp = requests.get(f"{GAMMA}/markets", params=param_set, timeout=10)
        if resp.status_code == 200:
            markets = resp.json()
            if markets and len(markets) > 0:
                q0 = markets[0].get('question', '')
                if 'gta' not in q0.lower():
                    print(f"  Params {param_set}: {len(markets)} markets")
                    for m in markets[:3]:
                        print(f"    - {m.get('question','')[:70]}")
                    break
        print(f"  Params {param_set}: {resp.status_code}, count={len(resp.json()) if resp.status_code==200 else 0}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 5: CLOB /prices?token_id (known BTC market from web)")
print("=" * 50)
try:
    # Try fetching the market by the event slug pattern we found
    resp = requests.get(f"{GAMMA}/events/btc-updown-5m", timeout=15)
    print(f"Gamma event by slug: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Response: {str(resp.json())[:500]}")
    else:
        print(f"  {resp.text[:200]}")
    
    # Also try with numeric ID from the URL
    resp2 = requests.get(f"{GAMMA}/events?id=btc-updown-5m-1779609900", timeout=15)
    print(f"\nGamma event by id: {resp2.status_code}")
    if resp2.status_code == 200:
        print(f"Response: {str(resp2.json())[:500]}")
except Exception as e:
    print(f"Failed: {e}")

print("\n" + "=" * 50)
print("TEST 6: Polymarket frontend data API")
print("=" * 50)
try:
    resp = requests.get("https://polymarket.com/api/events/btc-updown-5m", timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Response: {str(resp.json())[:500]}")
    else:
        # Try data API
        resp2 = requests.get(f"{CLOB}/markets?tag=crypto-prices", timeout=15)
        print(f"CLOB tag crypto-prices: {resp2.status_code}")
        if resp2.status_code == 200:
            print(f"Response: {str(resp2.json())[:500]}")
except Exception as e:
    print(f"Failed: {e}")
