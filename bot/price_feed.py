"""
BTC price feed using multiple public APIs with automatic fallback.
Tracks price changes and determines UP/DOWN state.
"""

import time
import requests
from datetime import datetime


class BTCPriceFeed:
    """
    Fetches BTC price data from multiple APIs (auto-fallback):
    1. CoinGecko (most reliable, no geo-blocks)
    2. Kraken (no geo-blocks)
    3. Coinbase (no geo-blocks)
    4. Binance (blocked in some regions)
    """

    def __init__(self, interval: str = "5m"):
        self.interval = interval
        self.last_price = None
        self.current_price = None
        self.price_history = []  # Store recent prices for candle simulation

    def get_current_price(self) -> float | None:
        """Get current BTC/USD price - tries multiple APIs."""
        apis = [
            self._get_coingecko_price,
            self._get_kraken_price,
            self._get_coinbase_price,
            self._get_binance_price,
        ]

        for api_func in apis:
            try:
                price = api_func()
                if price and price > 0:
                    return price
            except Exception:
                continue

        return None

    def _get_coingecko_price(self) -> float:
        """CoinGecko - free, no auth, rarely blocked."""
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "usd"}
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        data = response.json()
        return float(data["bitcoin"]["usd"])

    def _get_kraken_price(self) -> float:
        """Kraken - free public API, very reliable."""
        url = "https://api.kraken.com/0/public/Ticker"
        params = {"pair": "XBTUSD"}
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        data = response.json()
        # Kraken returns last trade price in 'c' field [price, volume]
        pair_key = list(data["result"].keys())[0]
        return float(data["result"][pair_key]["c"][0])

    def _get_coinbase_price(self) -> float:
        """Coinbase - free, no auth needed for spot price."""
        url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()
        return float(data["data"]["amount"])

    def _get_binance_price(self) -> float:
        """Binance - may be blocked in some regions."""
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbol": "BTCUSDT"}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data["price"])

    def get_recent_candles(self, limit: int = 50) -> list[dict]:
        """
        Get recent candle-like data.
        Tries Kraken first (public, no geo-block), then Binance.
        """
        # Try Kraken OHLC
        try:
            return self._get_kraken_candles(limit)
        except Exception:
            pass

        # Try Binance klines
        try:
            return self._get_binance_candles(limit)
        except Exception:
            pass

        # Last resort: build from live price polling (return empty)
        print("[PRICE] No candle API available - will build from live data")
        return []

    def _get_kraken_candles(self, limit: int = 50) -> list[dict]:
        """Kraken OHLC - free, reliable, no geo-block."""
        # Kraken interval: 5 = 5 minutes
        interval_map = {"1m": 1, "5m": 5, "15m": 15}
        interval = interval_map.get(self.interval, 5)

        url = "https://api.kraken.com/0/public/OHLC"
        params = {"pair": "XBTUSD", "interval": interval}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        pair_key = list(data["result"].keys())
        # Remove 'last' key
        pair_key = [k for k in pair_key if k != "last"][0]
        raw_candles = data["result"][pair_key]

        candles = []
        for c in raw_candles[-limit:]:
            candles.append({
                "timestamp": int(c[0]) * 1000,
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[6]),
            })
        return candles

    def _get_binance_candles(self, limit: int = 50) -> list[dict]:
        """Binance klines - may be blocked."""
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": "BTCUSDT",
            "interval": self.interval,
            "limit": limit,
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        candles = []
        for candle in data:
            candles.append({
                "timestamp": candle[0],
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
            })
        return candles

    def determine_state(self, candle: dict) -> str:
        """Determine if a candle is UP or DOWN."""
        if candle["close"] >= candle["open"]:
            return "UP"
        return "DOWN"

    def get_states_from_candles(self, candles: list[dict]) -> list[str]:
        """Convert candle list to state list."""
        return [self.determine_state(c) for c in candles]

    def update(self) -> str | None:
        """
        Fetch latest price and return state change.

        Returns:
            'UP' or 'DOWN' if price changed, None if no update
        """
        price = self.get_current_price()
        if price is None:
            return None

        self.last_price = self.current_price
        self.current_price = price

        # Store for history
        self.price_history.append({
            "price": price,
            "time": time.time(),
        })
        # Keep last 200 only
        if len(self.price_history) > 200:
            self.price_history = self.price_history[-200:]

        if self.last_price is None:
            return None

        if self.current_price > self.last_price:
            return "UP"
        elif self.current_price < self.last_price:
            return "DOWN"
        else:
            # Price exactly same - use last known direction or UP
            return "UP"
