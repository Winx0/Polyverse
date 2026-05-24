"""
Polymarket CLOB v2 client for BTC Up/Down market.
Handles authentication, market discovery, and order placement.
"""

import os
import json
import time
import requests
from eth_account import Account
from datetime import datetime


class PolymarketClient:
    """
    Client for Polymarket CLOB v2 API.
    Handles:
    - API authentication (L1 + L2 auth)
    - Market discovery (BTC Up/Down)
    - Order placement (market buy YES/NO)
    - Balance checking
    """

    CLOB_HOST = "https://clob.polymarket.com"
    GAMMA_HOST = "https://gamma-api.polymarket.com"

    def __init__(self, private_key: str, safe_address: str = None):
        """
        Args:
            private_key: Ethereum private key (0x prefixed)
            safe_address: Polymarket Safe/proxy wallet address (optional)
        """
        self.private_key = private_key
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.safe_address = safe_address or self.address
        self.api_key = None
        self.api_secret = None
        self.api_passphrase = None
        self.session = requests.Session()

    def authenticate(self) -> bool:
        """
        Authenticate with Polymarket CLOB v2.
        Gets API credentials for trading.

        Returns:
            True if authenticated successfully
        """
        try:
            # Step 1: Derive API credentials
            # The CLOB v2 uses a signature-based auth
            timestamp = int(time.time())
            message = f"Polymarket CLOB API\nTimestamp: {timestamp}"

            # Sign the message
            from eth_account.messages import encode_defunct
            msg = encode_defunct(text=message)
            signed = self.account.sign_message(msg)

            # Step 2: Register/login to get API keys
            url = f"{self.CLOB_HOST}/auth/api-key"
            payload = {
                "address": self.address,
                "timestamp": timestamp,
                "signature": signed.signature.hex(),
            }

            response = self.session.post(url, json=payload, timeout=15)

            if response.status_code == 200:
                data = response.json()
                self.api_key = data.get("apiKey")
                self.api_secret = data.get("secret")
                self.api_passphrase = data.get("passphrase")
                print(f"[AUTH] Authenticated as {self.address[:10]}...")
                return True
            else:
                print(f"[AUTH] Failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"[AUTH] Error: {e}")
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

        Args:
            market: Market dict from find_btc_market()
            side: 'YES' or 'NO'

        Returns:
            Current price (0.0 to 1.0)
        """
        try:
            token_id = market["yes_token_id"] if side == "YES" else market["no_token_id"]
            url = f"{self.CLOB_HOST}/price"
            params = {"token_id": token_id, "side": "buy"}

            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data.get("price", 0.5))
        except Exception as e:
            print(f"[PRICE] Error: {e}")

        # Fallback to market data
        return market.get(f"{side.lower()}_price", 0.5)

    def get_balance(self) -> float:
        """Get collateral balance (USDC) on Polymarket."""
        try:
            url = f"{self.CLOB_HOST}/balance"
            headers = self._get_auth_headers()
            response = self.session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return float(data.get("balance", 0))
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
        try:
            url = f"{self.CLOB_HOST}/order"
            headers = self._get_auth_headers()

            payload = {
                "tokenID": token_id,
                "amount": str(amount),
                "side": side,
                "type": "market",
                "feeRateBps": "0",  # Taker fee handled by protocol
            }

            response = self.session.post(url, json=payload, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                print(f"[ORDER] Placed {side} ${amount} - ID: {data.get('orderID', 'unknown')}")
                return data
            else:
                print(f"[ORDER] Failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"[ORDER] Error: {e}")
            return None

    def _get_auth_headers(self) -> dict:
        """Generate authenticated headers for CLOB v2."""
        if not self.api_key:
            return {}

        timestamp = str(int(time.time()))
        return {
            "POLY-ADDRESS": self.address,
            "POLY-API-KEY": self.api_key,
            "POLY-SECRET": self.api_secret or "",
            "POLY-PASSPHRASE": self.api_passphrase or "",
            "POLY-TIMESTAMP": timestamp,
        }
