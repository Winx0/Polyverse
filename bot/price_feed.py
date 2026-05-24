"""
BTC price feed using public APIs.
Tracks 5-minute candles and determines UP/DOWN state.
"""

import time
import requests
from datetime import datetime


class BTCPriceFeed:
    """
    Fetches BTC price data from public APIs (Binance, CoinGecko fallback).
    Determines directional state for Markov model input.
    """

    BINANCE_API = "https://api.binance.com/api/v3"
    COINGECKO_API = "https://api.coingecko.com/api/v3"

    def __init__(self, interval: str = "5m"):
        """
        Args:
            interval: Candle interval ('1m', '5m', '15m')
        """
        self.interval = interval
        self.last_price = None
        self.current_price = None

    def get_current_price(self) -> float | None:
        """Get current BTC/USDT price."""
        try:
            return self._get_binance_price()
        except Exception:
            try:
                return self._get_coingecko_price()
            except Exception:
                return None

    def _get_binance_price(self) -> float:
        """Fetch from Binance public API (no auth needed)."""
        url = f"{self.BINANCE_API}/ticker/price"
        params = {"symbol": "BTCUSDT"}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return float(data["price"])

    def _get_coingecko_price(self) -> float:
        """Fallback: CoinGecko free API."""
        url = f"{self.COINGECKO_API}/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "usd"}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return float(data["bitcoin"]["usd"])

    def get_recent_candles(self, limit: int = 50) -> list[dict]:
        """
        Get recent candle data from Binance.

        Returns list of dicts with: open, close, high, low, timestamp
        """
        url = f"{self.BINANCE_API}/klines"
        params = {
            "symbol": "BTCUSDT",
            "interval": self.interval,
            "limit": limit,
        }
        response = requests.get(url, params=params, timeout=10)
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

        if self.last_price is None:
            return None

        if self.current_price >= self.last_price:
            return "UP"
        return "DOWN"
