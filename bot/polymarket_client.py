"""
Polymarket CLOB v2 client for BTC Up/Down market.
Uses py_clob_client_v2 with V2 deposit wallet (signature_type=3, POLY_1271).
"""

import os
import json
import time
import requests

try:
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2.clob_types import (
        ApiCreds, OrderArgs, MarketOrderArgs, OrderType,
    )
    from py_clob_client_v2.constants import POLYGON
    HAS_CLOB_CLIENT = True
except ImportError:
    HAS_CLOB_CLIENT = False


class PolymarketClient:
    """Polymarket CLOB v2 client (V2 deposit wallet flow)."""

    CLOB_HOST = "https://clob.polymarket.com"
    GAMMA_HOST = "https://gamma-api.polymarket.com"

    def __init__(self, private_key: str, safe_address: str = None,
                 api_key: str = "", api_secret: str = "", api_passphrase: str = ""):
        self.private_key = private_key
        self.safe_address = safe_address  # V2 deposit wallet address (funder)
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.client = None
        self.session = requests.Session()
        self._cached_market = None
        self._cache_time = 0

    def authenticate(self) -> bool:
        """Authenticate with Polymarket CLOB v2 using deposit wallet flow."""
        if not HAS_CLOB_CLIENT:
            print("[AUTH] py_clob_client_v2 not installed!")
            return False

        if not self.safe_address:
            print("[AUTH] SAFE_ADDRESS (deposit wallet funder) required!")
            return False

        try:
            creds = None
            if self.api_key and self.api_secret and self.api_passphrase:
                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase,
                )

            # If no creds, derive them
            if not creds:
                init_client = ClobClient(
                    host=self.CLOB_HOST,
                    chain_id=POLYGON,
                    key=self.private_key,
                    signature_type=3,
                    funder=self.safe_address,
                )
                creds = init_client.create_or_derive_api_key()
                self.api_key = creds.api_key
                self.api_secret = creds.api_secret
                self.api_passphrase = creds.api_passphrase
                print(f"[AUTH] Derived API key: {creds.api_key[:10]}...")

            # Init authenticated client (V2 deposit wallet, sig_type=3)
            self.client = ClobClient(
                host=self.CLOB_HOST,
                chain_id=POLYGON,
                key=self.private_key,
                creds=creds,
                signature_type=3,
                funder=self.safe_address,
            )
            print(f"[AUTH] Authenticated! Funder: {self.safe_address[:10]}...")
            return True

        except Exception as e:
            print(f"[AUTH] Failed: {e}")
            return False

    def find_btc_market(self) -> dict | None:
        """Find active BTC 5-min Up/Down market via dynamic slug."""
        if self._cached_market and (time.time() - self._cache_time < 30):
            return self._cached_market

        market = None
        current_ts = int(time.time())
        current_window = (current_ts // 300) * 300

        slugs_to_try = [
            f"btc-updown-5m-{current_window + 600}",
            f"btc-updown-5m-{current_window + 300}",
            f"btc-updown-5m-{current_window + 900}",
            f"btc-updown-5m-{current_window}",
        ]

        for slug in slugs_to_try:
            try:
                response = self.session.get(
                    f"{self.GAMMA_HOST}/events",
                    params={"slug": slug},
                    timeout=10,
                )
                if response.status_code != 200:
                    continue
                events = response.json()
                if not events:
                    continue

                m = events[0].get("markets", [{}])[0]
                if m.get("closed", False):
                    continue

                end_date = m.get("endDate", "")
                if end_date:
                    try:
                        from datetime import datetime, timezone
                        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                        if end_dt < datetime.now(timezone.utc):
                            continue
                    except Exception:
                        pass

                clob_ids = m.get("clobTokenIds", [])
                if isinstance(clob_ids, str):
                    try:
                        clob_ids = json.loads(clob_ids)
                    except Exception:
                        clob_ids = []
                if len(clob_ids) < 2:
                    continue

                up_price = down_price = 0.5
                prices_raw = m.get("outcomePrices", "")
                if prices_raw:
                    try:
                        if isinstance(prices_raw, str):
                            prices = json.loads(prices_raw) if prices_raw.startswith("[") else prices_raw.split(",")
                        else:
                            prices = prices_raw
                        up_price = float(prices[0])
                        down_price = float(prices[1])
                    except Exception:
                        pass

                if up_price >= 0.95 or down_price >= 0.95:
                    continue

                market = {
                    "id": m.get("id"),
                    "condition_id": m.get("conditionId", ""),
                    "question": m.get("question", ""),
                    "yes_token_id": clob_ids[0],
                    "no_token_id": clob_ids[1],
                    "yes_price": up_price,
                    "no_price": down_price,
                    "volume": m.get("volume", 0),
                    "end_date": end_date,
                }
                print(f"[MARKET] {market['question'][:50]} | UP={up_price:.3f} DOWN={down_price:.3f}")
                break
            except Exception:
                continue

        if market:
            self._cached_market = market
            self._cache_time = time.time()
        else:
            print("[MARKET] No active BTC market found")
        return market

    def get_market_price(self, market: dict, side: str = "YES") -> float:
        """Get live price from orderbook."""
        try:
            token_id = market["yes_token_id"] if side == "YES" else market["no_token_id"]
            if self.client and token_id:
                book = self.client.get_order_book(token_id)
                if book:
                    if book.asks and len(book.asks) > 0:
                        price = float(book.asks[0].price)
                        if 0.01 < price < 0.99:
                            return price
                    if book.bids and len(book.bids) > 0:
                        price = float(book.bids[0].price)
                        if 0.01 < price < 0.99:
                            return price
        except Exception as e:
            if "404" not in str(e):
                print(f"[PRICE] Error: {str(e)[:80]}")

        fallback = market.get(f"{side.lower()}_price", 0.5)
        return fallback if 0.01 < fallback < 0.99 else 0.5

    def place_market_order(self, token_id: str, amount: float, side: str = "BUY") -> dict | None:
        """
        Place a MARKET order (FOK) on Polymarket V2.
        amount = USD amount to spend.
        """
        if not self.client:
            print("[ORDER] Client not authenticated")
            return None

        try:
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=side,
                order_type=OrderType.FOK,
            )
            result = self.client.create_and_post_market_order(
                order_args, order_type=OrderType.FOK,
            )
            if result:
                status = result.get("status", "?") if isinstance(result, dict) else "?"
                print(f"[ORDER] {side} ${amount:.2f} → status={status}")
                return result
            print("[ORDER] No result returned")
            return None
        except Exception as e:
            print(f"[ORDER] Error: {str(e)[:200]}")
            return None
