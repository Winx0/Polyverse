"""Debug script - find what markets are available."""
import os
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

print("Fetching markets...")
resp = client.get_markets()
print(f"Type: {type(resp)}")

if isinstance(resp, dict):
    print(f"Keys: {list(resp.keys())}")
    data = resp.get('data', resp.get('markets', []))
else:
    data = resp

print(f"Count: {len(data) if hasattr(data, '__len__') else 'unknown'}")

# Print first 5 markets
for i, m in enumerate(data):
    if i >= 5:
        break
    if isinstance(m, dict):
        q = m.get('question', 'NO QUESTION')
        cid = m.get('condition_id', m.get('conditionId', 'NO ID'))
        tokens = m.get('tokens', [])
        print(f"\n--- Market {i} ---")
        print(f"  Question: {q}")
        print(f"  ID: {cid}")
        print(f"  Tokens: {len(tokens)}")
        if tokens:
            print(f"  Token0: {tokens[0]}")
    else:
        print(f"\n--- Market {i} ---")
        print(f"  Type: {type(m)}")
        print(f"  Value: {str(m)[:200]}")

# Search for BTC
print("\n\n=== SEARCHING FOR BTC ===")
found = 0
for m in data:
    if isinstance(m, dict):
        q = str(m.get('question', '')).lower()
        if 'btc' in q or 'bitcoin' in q:
            found += 1
            print(f"  FOUND: {m.get('question', '')}")
            print(f"    Tokens: {m.get('tokens', [])}")
            if found >= 5:
                break

if found == 0:
    print("  No BTC markets found in response!")
