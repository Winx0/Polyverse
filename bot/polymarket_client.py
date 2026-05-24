"""
Polymarket CLOB v2 client for BTC Up/Down market.
Uses py_clob_client with pre-generated API credentials.
"""

import os
import json
import time
import requests
from datetime import datetime

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
    from py_clob_client.constants import POLYGON
    HAS_CLOB_CLIENT = True
except ImportError:
    HAS_CLOB_CLIENT = False


class PolymarketClient:
    """
    Client for Polymarket CLOB v2 API.
    Uses py_clob_client with pre-generated API credentials.
    """

    CLOB_HOST = "https://clob.polymarket.com"
    GAMMA_HOST = "https://gamma-api.polymarket.com"

    def __init__(self, private_key: str, safe_address: str = None,
                 api_key: str = "", api_secret: str = "", api_passphrase: str = ""):
        """
        Args:
            private_key: Ethereum private key (0x prefixed)
            safe_address: Polymarket Safe/proxy wallet address
            api_key: Pre-generated CLOB API key
            api_secret: Pre-generated CLOB API secret
            api_passphrase: Pre-generated CLOB API passphrase
        """
        self.private_key = private_key
        self.safe_address = safe_address
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.client = None
        self.session = requests.Session()

    def authenticate(self) -> bool:
        """
        Authenticate with Polymarket CLOB v2 using pre-generated API creds.

        Returns:
            True if authenticated successfully
        """
        if not HAS_CLOB_CLIENT:
            print("[AUTH] py_clob_client not installed!")
            return False

        try:
            # Use pre-generated API credentials
            if self.api_key and self.api_secret and self.api_passphrase:
                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase,
                )

                self.client = ClobClient(
                    host=self.CLOB_HOST,
                    chain_id=POLYGON,
                    key=self.private_key,
                    creds=creds,
                )
            else:
                # Try without creds (will derive)
                self.client = ClobClient(
                    host=self.CLOB_HOST,
                    chain_id=POLYGON,
                    key=self.private_key,
                )
                # Derive API key
                creds = self.client.derive_api_key()
                self.client = ClobClient(
                    host=self.CLOB_HOST,
                    chain_id=POLYGON,
                    key=self.private_key,
                    creds=creds,
                )

            # Test connection
            print(f"[AUTH] Authenticated successfully!")
            return True

        except Exception as e:
            print(f"[AUTH] Failed: {e}")
            return False

    def find_btc_market(self) -> dict | None:
        """
        Find the active BTC 5-minute Up/Down market.
        Uses dynamic slug based on current timestamp (rolling 5-min windows).
        """
        # Use cache if fresh (< 30 seconds)
        if hasattr(self, '_cached_market') and self._cached_market and \
           (time.time() - self._cache_time < 30):
            return self._cached_market

        market = None

        # BTC 5m markets use slug: btc-updown-5m-{unix_timestamp}
        # Timestamp is rounded to nearest 300 seconds (5 minutes)
        current_ts = int(time.time())
        current_window = (current_ts // 300) * 300
        next_window = current_window + 300

        # Try current and next window slugs
        slugs_to_try = [
            f"btc-updown-5m-{current_window}",
            f"btc-updown-5m-{next_window}",
            f"btc-updown-5m-{current_window - 300}",
        ]

        for slug in slugs_to_try:
            try:
                url = f"{self.GAMMA_HOST}/events"
                params = {"slug": slug}
                response = self.session.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    events = response.json()
                    if events and len(events) > 0:
                        event = events[0]
                        markets = event.get("markets", [])
                        if markets:
                            m = markets[0]
                            print(f"[MARKET] Found: {m.get('question', '')[:60]} (slug={slug})")
                            market = self._parse_market(m)
                            break
            except Exception as e:
                continue

        # Fallback: try fetching event directly by slug
        if not market:
            for slug in slugs_to_try:
                try:
                    url = f"{self.GAMMA_HOST}/events/{slug}"
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        event = response.json()
                        markets = event.get("markets", [])
                        if markets:
                            m = markets[0]
                            print(f"[MARKET] Found: {m.get('question', '')[:60]}")
                            market = self._parse_market(m)
                            break
                except Exception:
                    continue

        if market:
            self._cached_market = market
            self._cache_time = time.time()
            return market

        print(f"[MARKET] No BTC Up/Down market found (tried slugs: {slugs_to_try[0]})")
        return None

    def _parse_market(self, market: dict) -> dict:
        """Parse raw market data into usable format."""
        tokens = market.get("tokens", [])
        yes_token = None
        no_token = None

        for token in tokens:
            outcome = str(token.get("outcome", "")).lower()
            if outcome in ("yes", "up"):
                yes_token = token
            elif outcome in ("no", "down"):
                no_token = token

        # If tokens not found by outcome, try clobTokenIds
        if not yes_token and not no_token:
            clob_ids = market.get("clobTokenIds", [])
            if len(clob_ids) >= 2:
                yes_token = {"token_id": clob_ids[0], "price": 0.5}
                no_token = {"token_id": clob_ids[1], "price": 0.5}
            elif len(tokens) >= 2:
                yes_token = tokens[0]
                no_token = tokens[1]

        return {
            "id": market.get("id") or market.get("condition_id") or market.get("conditionId"),
            "condition_id": market.get("conditionId") or market.get("condition_id"),
            "question": market.get("question"),
            "yes_token_id": yes_token.get("token_id") if yes_token else None,
            "no_token_id": no_token.get("token_id") if no_token else None,
            "yes_price": float(yes_token.get("price", 0.5)) if yes_token else 0.5,
            "no_price": float(no_token.get("price", 0.5)) if no_token else 0.5,
            "volume": market.get("volume", 0),
            "end_date": market.get("endDate") or market.get("end_date_iso"),
        }

    def get_market_price(self, market: dict, side: str = "YES") -> float:
        """
        Get current market price for YES or NO.
        """
        try:
            token_id = market["yes_token_id"] if side == "YES" else market["no_token_id"]

            if self.client:
                # Use py_clob_client
                book = self.client.get_order_book(token_id)
                if book and book.asks:
                    return float(book.asks[0].price)
                if book and book.bids:
                    return float(book.bids[0].price)
        except Exception as e:
            print(f"[PRICE] Error: {e}")

        # Fallback to market data
        return market.get(f"{side.lower()}_price", 0.5)

    def get_balance(self) -> float:
        """Get collateral balance (USDC) on Polymarket."""
        try:
            if self.client:
                balance = self.client.get_balance_allowance()
                if balance:
                    return float(balance.get("balance", 0)) / 1e6  # USDC has 6 decimals
        except Exception as e:
            print(f"[BALANCE] Error: {e}")
        return 0.0

    def place_market_order(self, token_id: str, amount: float, side: str = "BUY") -> dict | None:
        """
        Place a market order on CLOB v2.

        Args:
            token_id: Token ID to trade
            amount: Dollar amount to spend
            side: 'BUY' or 'SELL'

        Returns:
            Order result dict or None if failed
        """
        if not self.client:
            print("[ORDER] Client not authenticated")
            return None

        try:
            # Create market buy order using py_clob_client
            order_args = OrderArgs(
                token_id=token_id,
                amount=amount,
                side=side,
            )

            # Place as market order (FOK - Fill or Kill)
            result = self.client.create_and_post_order(order_args)

            if result:
                print(f"[ORDER] Placed {side} ${amount} - Result: {result}")
                return result
            else:
                print(f"[ORDER] No result returned")
                return None

        except Exception as e:
            print(f"[ORDER] Error: {e}")
            return None
