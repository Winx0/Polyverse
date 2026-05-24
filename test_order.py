"""
Test single order placement on Polymarket.
Places 1 small order ($0.25) on the current BTC Up/Down market.
Run: python test_order.py
"""
import os
import time
import json
from dotenv import load_dotenv
load_dotenv('.env.bot')

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from py_clob_client.constants import POLYGON
import requests

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
print("  TEST ORDER - 1 trade $0.25")
print("=" * 50)

# Find current market
current_ts = int(time.time())
current_window = (current_ts // 300) * 300
GAMMA = "https://gamma-api.polymarket.com"

market = None
for offset in [600, 300, 900]:
    slug = f"btc-updown-5m-{current_window + offset}"
    try:
        r = requests.get(f"{GAMMA}/events", params={"slug": slug}, timeout=10)
        if r.status_code == 200:
            events = r.json()
            if events:
                m = events[0]['markets'][0]
                if not m.get('closed', False):
                    clob_ids = m.get('clobTokenIds', [])
                    if isinstance(clob_ids, str):
                        clob_ids = json.loads(clob_ids)
                    if len(clob_ids) >= 2:
                        market = m
                        print(f"\n[OK] Market: {m['question']}")
                        print(f"[OK] UP token: {clob_ids[0][:30]}...")
                        print(f"[OK] DOWN token: {clob_ids[1][:30]}...")
                        break
    except Exception:
        continue

if not market:
    print("[ERROR] No active market found!")
    exit(1)

# Place order on UP token (buy YES on BTC going up)
clob_ids = market.get('clobTokenIds', [])
if isinstance(clob_ids, str):
    clob_ids = json.loads(clob_ids)

token_id = clob_ids[0]  # UP token
amount = 0.25  # $0.25 test

print(f"\n[ORDER] Placing BUY $0.25 on UP token...")
print(f"[ORDER] Token: {token_id[:30]}...")

try:
    # First check what OrderArgs expects
    from py_clob_client.clob_types import OrderArgs, OrderType
    import inspect
    print(f"[DEBUG] OrderArgs params: {inspect.signature(OrderArgs)}")

    # Try with price parameter (limit order at market price)
    # price=0.50 means we pay $0.50 per share
    order_args = OrderArgs(
        price=0.50,
        size=amount,
        side="BUY",
        token_id=token_id,
    )
    print(f"[DEBUG] Order args created successfully")

    result = client.create_and_post_order(order_args)
    print(f"\n[RESULT] {result}")
    print("\n SUCCESS! Order placed on Polymarket!")
except TypeError as e:
    print(f"\n[ERROR] TypeError: {e}")
    # Try alternative method
    try:
        print("\n[RETRY] Trying create_order + post...")
        order = client.create_order(order_args)
        print(f"[DEBUG] Order created: {order}")
        result = client.post_order(order)
        print(f"[RESULT] {result}")
    except Exception as e2:
        print(f"[ERROR] Retry failed: {e2}")
except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\n[INFO] This might mean:")
    print("  - Not enough USDC balance")
    print("  - Market not accepting orders yet")
    print("  - Order size too small (min $1 on some markets)")
    print("  - Need to approve USDC spending first")
