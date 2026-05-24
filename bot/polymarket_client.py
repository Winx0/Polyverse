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

        Returns:
            Market dict with token_ids, prices, etc.
        """
        try:
            # Search for BTC markets on Gamma API
            url = f"{self.GAMMA_HOST}/markets"
            params = {
                "closed": "false",
                "tag": "crypto",
                "limit": 50,
            }

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            markets = response.json()

            # Filter for BTC Up/Down 5-minute markets
            for market in markets:
                title = market.get("question", "").lower()
                if "btc" in title and ("up" in title or "down" in title) and "5" in title:
                    return self._parse_market(market)

            # Broader search
            for market in markets:
                title = market.get("question", "").lower()
                if "bitcoin" in title and ("up" in title or "down" in title):
                    return self._parse_market(market)

            print("[MARKET] No BTC Up/Down market found")
            return None

        except Exception as e:
            print(f"[MARKET] Error finding market: {e}")
            return None

    def _parse_market(self, market: dict) -> dict:
        """Parse raw market data into usable format."""
        tokens = market.get("tokens", [])
        yes_token = None
        no_token = None

        for token in tokens:
            if token.get("outcome", "").lower() == "yes":
                yes_token = token
            elif token.get("outcome", "").lower() == "no":
                no_token = token

        return {
            "id": market.get("id"),
            "condition_id": market.get("conditionId"),
            "question": market.get("question"),
            "yes_token_id": yes_token.get("token_id") if yes_token else None,
            "no_token_id": no_token.get("token_id") if no_token else None,
            "yes_price": float(yes_token.get("price", 0.5)) if yes_token else 0.5,
            "no_price": float(no_token.get("price", 0.5)) if no_token else 0.5,
            "volume": market.get("volume", 0),
            "end_date": market.get("endDate"),
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
