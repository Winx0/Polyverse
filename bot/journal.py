"""
Trade journal - logs all signals, entries, exits, and P/L.
Used by the self-learning loop for strategy improvement.
"""

import json
import os
from datetime import datetime
from pathlib import Path


class TradeJournal:
    """
    Persistent trade journal that logs:
    - Every signal detected (entry/skip)
    - Trade entries with Markov state
    - Trade exits with P/L
    - Session summaries
    """

    def __init__(self, journal_dir: str = "data/journal"):
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.today_file = self.journal_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        self.trades = self._load_today()

    def _load_today(self) -> list:
        """Load today's journal entries."""
        if self.today_file.exists():
            with open(self.today_file, "r") as f:
                return json.load(f)
        return []

    def _save(self):
        """Save journal to disk."""
        with open(self.today_file, "w") as f:
            json.dump(self.trades, f, indent=2, default=str)

    def log_signal(self, signal: dict):
        """
        Log a trading signal (whether entered or skipped).

        Args:
            signal: Dict with keys like:
                - timestamp, state, persistence_prob, market_price,
                - edge, action ('ENTER'/'SKIP'), reason
        """
        entry = {
            "type": "signal",
            "timestamp": datetime.now().isoformat(),
            **signal,
        }
        self.trades.append(entry)
        self._save()

    def log_trade_entry(self, trade: dict):
        """
        Log a trade entry.

        Args:
            trade: Dict with keys like:
                - timestamp, market_id, side, entry_price,
                - bet_size, kelly_fraction, markov_state,
                - persistence_prob
        """
        entry = {
            "type": "entry",
            "timestamp": datetime.now().isoformat(),
            **trade,
        }
        self.trades.append(entry)
        self._save()

    def log_trade_exit(self, trade: dict):
        """
        Log a trade exit/resolution.

        Args:
            trade: Dict with keys like:
                - timestamp, market_id, outcome ('WIN'/'LOSS'),
                - pnl, exit_price
        """
        entry = {
            "type": "exit",
            "timestamp": datetime.now().isoformat(),
            **trade,
        }
        self.trades.append(entry)
        self._save()

    def get_today_summary(self) -> dict:
        """Get summary statistics for today."""
        entries = [t for t in self.trades if t["type"] == "entry"]
        exits = [t for t in self.trades if t["type"] == "exit"]
        signals = [t for t in self.trades if t["type"] == "signal"]

        wins = [e for e in exits if e.get("outcome") == "WIN"]
        losses = [e for e in exits if e.get("outcome") == "LOSS"]

        total_pnl = sum(e.get("pnl", 0) for e in exits)
        win_rate = len(wins) / len(exits) if exits else 0

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "signals_detected": len(signals),
            "trades_entered": len(entries),
            "trades_resolved": len(exits),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 4),
            "total_pnl": round(total_pnl, 4),
            "avg_pnl_per_trade": round(total_pnl / len(exits), 4) if exits else 0,
        }

    def get_all_entries(self) -> list:
        """Get all journal entries for today."""
        return self.trades

    def get_history(self, days: int = 7) -> list[dict]:
        """Load journal summaries for past N days."""
        summaries = []
        for file in sorted(self.journal_dir.glob("*.json")):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                exits = [t for t in data if t.get("type") == "exit"]
                wins = [e for e in exits if e.get("outcome") == "WIN"]
                total_pnl = sum(e.get("pnl", 0) for e in exits)

                summaries.append({
                    "date": file.stem,
                    "trades": len(exits),
                    "win_rate": len(wins) / len(exits) if exits else 0,
                    "pnl": total_pnl,
                })
            except Exception:
                continue

        return summaries[-days:]
