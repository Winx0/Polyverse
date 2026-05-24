"""
Main trading engine - orchestrates all components.
Runs the trading loop: fetch data -> analyze -> decide -> execute.
"""

import os
import time
import json
from datetime import datetime
from pathlib import Path

from bot.markov import MarkovModel
from bot.kelly import KellySizer
from bot.price_feed import BTCPriceFeed
from bot.polymarket_client import PolymarketClient
from bot.journal import TradeJournal
from bot.telegram_notifier import TelegramNotifier


class TradingEngine:
    """
    Main orchestrator for the BTC Up/Down trading bot.
    """

    def __init__(self, config: dict):
        self.config = config
        self.dry_run = config.get("DRY_RUN", True)
        self.min_edge = config.get("MIN_EDGE", 0.05)
        self.min_prob = config.get("MIN_PROB", 0.87)
        self.bankroll = config.get("BANKROLL", 2.0)
        self.loop_interval = config.get("LOOP_INTERVAL", 81)

        # Initialize components
        self.markov = MarkovModel(window_size=50)
        self.kelly = KellySizer(
            max_fraction=0.50,
            min_bet=config.get("MIN_BET", 0.10),
            max_bet=config.get("MAX_BET", 2.00),
        )
        self.price_feed = BTCPriceFeed(interval="5m")
        self.journal = TradeJournal()
        self.telegram = TelegramNotifier(
            bot_token=config.get("TELEGRAM_BOT_TOKEN", ""),
            chat_id=config.get("TELEGRAM_CHAT_ID", ""),
        )

        # Polymarket client (only init if not dry run)
        self.client = None
        if not self.dry_run:
            pk = config.get("PRIVATE_KEY", "")
            if pk:
                self.client = PolymarketClient(
                    private_key=pk,
                    safe_address=config.get("SAFE_ADDRESS"),
                )

        self.running = False
        self.trades_today = 0
        self.signals_today = 0

    def start(self):
        """Start the trading loop."""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        print(f"\n{'='*50}")
        print(f"  POLYMARKET BTC UP/DOWN BOT")
        print(f"  Mode: {mode}")
        print(f"  Bankroll: ${self.bankroll:.2f}")
        print(f"  Min Edge: {self.min_edge:.0%}")
        print(f"  Min Persistence: {self.min_prob:.0%}")
        print(f"  Loop Interval: {self.loop_interval}s")
        print(f"{'='*50}\n")

        self.telegram.notify_startup(self.bankroll, mode)

        # Warm up Markov model with historical data
        self._warmup()

        # Authenticate if live
        if self.client and not self.dry_run:
            if not self.client.authenticate():
                print("[ENGINE] Auth failed. Switching to DRY_RUN.")
                self.dry_run = True

        self.running = True
        self._run_loop()

    def _warmup(self):
        """Load historical candles to initialize Markov model."""
        print("[ENGINE] Warming up Markov model...")
        try:
            candles = self.price_feed.get_recent_candles(limit=50)
            states = self.price_feed.get_states_from_candles(candles)
            for state in states:
                self.markov.add_observation(state)
            print(f"[ENGINE] Loaded {len(states)} historical states")
            matrix = self.markov.get_transition_matrix()
            print(f"[ENGINE] P(UP|UP)={matrix['P(UP|UP)']:.3f}")
            print(f"[ENGINE] P(DOWN|DOWN)={matrix['P(DOWN|DOWN)']:.3f}")
        except Exception as e:
            print(f"[ENGINE] Warmup failed: {e}")
            print("[ENGINE] Will build model from live data...")

    def _run_loop(self):
        """Main trading loop."""
        print("\n[ENGINE] Starting trading loop...\n")

        while self.running:
            try:
                self._tick()
            except KeyboardInterrupt:
                print("\n[ENGINE] Stopped by user.")
                self.running = False
            except Exception as e:
                print(f"[ENGINE] Error in loop: {e}")
                self.telegram.notify_error(str(e))
                time.sleep(10)

            time.sleep(self.loop_interval)

        # Final summary
        self._print_summary()

    def _tick(self):
        """Single iteration of the trading loop."""
        # 1. Get latest price state
        state = self.price_feed.update()
        if state is None:
            return

        # 2. Update Markov model
        self.markov.add_observation(state)

        if not self.markov.has_enough_data():
            return

        # 3. Get persistence probability
        current_state = self.markov.get_current_state()
        persistence = self.markov.get_persistence_probability(current_state)

        # 4. Check entry conditions
        signal = self._evaluate_signal(current_state, persistence)
        self.signals_today += 1

        if signal["action"] == "ENTER":
            self._execute_trade(signal)

    def _evaluate_signal(self, state: str, persistence: float) -> dict:
        """Evaluate whether to enter a trade."""
        # Simulate market price (in dry run) or fetch real
        market_price = 0.50  # Default

        if self.client and not self.dry_run:
            market = self.client.find_btc_market()
            if market:
                side = "YES" if state == "UP" else "NO"
                market_price = self.client.get_market_price(market, side)
        else:
            # In dry run, simulate market price based on persistence
            # Market usually prices between 0.45-0.65
            import random
            market_price = 0.45 + random.random() * 0.20

        # Calculate edge
        edge = persistence - market_price

        # Build signal
        signal = {
            "state": state,
            "persistence_prob": persistence,
            "market_price": market_price,
            "edge": edge,
            "action": "SKIP",
            "reason": "",
        }

        # Entry conditions
        if persistence < self.min_prob:
            signal["reason"] = f"persistence {persistence:.3f} < {self.min_prob}"
        elif edge < self.min_edge:
            signal["reason"] = f"edge {edge:.3f} < {self.min_edge}"
        elif self.bankroll < self.kelly.min_bet:
            signal["reason"] = f"bankroll ${self.bankroll:.2f} < min bet"
        else:
            signal["action"] = "ENTER"
            signal["reason"] = "conditions met"

        # Log signal
        self.journal.log_signal(signal)

        status = ">>>" if signal["action"] == "ENTER" else "   "
        print(
            f"{status} [{datetime.now().strftime('%H:%M:%S')}] "
            f"State={state} P={persistence:.3f} "
            f"Q={market_price:.3f} Edge={edge:.3f} "
            f"-> {signal['action']} ({signal['reason']})"
        )

        return signal

    def _execute_trade(self, signal: dict):
        """Execute a trade based on the signal."""
        p = signal["persistence_prob"]
        q = signal["market_price"]

        # Calculate position size
        bet_size = self.kelly.calculate_bet_size(p, q, self.bankroll)

        if bet_size <= 0:
            print(f"    Kelly says no bet (f*=0)")
            return

        ev = self.kelly.calculate_expected_value(p, q, bet_size)
        side = "YES" if signal["state"] == "UP" else "NO"

        print(f"    >>> ENTRY: {side} @ {q:.3f} | Bet: ${bet_size:.2f} | EV: ${ev:.4f}")

        # Log entry
        self.journal.log_trade_entry({
            "side": side,
            "entry_price": q,
            "bet_size": bet_size,
            "kelly_fraction": self.kelly.calculate_kelly_fraction(p, q),
            "markov_state": signal["state"],
            "persistence_prob": p,
            "expected_value": ev,
        })

        # Notify
        self.telegram.notify_trade_entry(side, q, bet_size, p, signal["edge"])

        # Execute (or simulate)
        if self.dry_run:
            self._simulate_outcome(signal, bet_size)
        else:
            self._live_execute(signal, bet_size)

        self.trades_today += 1

    def _simulate_outcome(self, signal: dict, bet_size: float):
        """Simulate trade outcome for DRY_RUN mode."""
        import random

        # Use persistence probability as the actual win chance
        p = signal["persistence_prob"]
        won = random.random() < p

        if won:
            q = signal["market_price"]
            shares = bet_size / q
            pnl = shares * (1 - q) - bet_size + bet_size  # profit
            pnl = bet_size * ((1 - q) / q)  # simplified
            outcome = "WIN"
        else:
            pnl = -bet_size
            outcome = "LOSS"

        self.bankroll += pnl

        self.journal.log_trade_exit({
            "outcome": outcome,
            "pnl": round(pnl, 4),
            "bankroll_after": round(self.bankroll, 4),
        })

        self.telegram.notify_trade_exit(outcome, pnl, self.bankroll)

        emoji = "WIN" if won else "LOSS"
        print(f"    <<< {emoji}: P/L ${pnl:+.4f} | Bankroll: ${self.bankroll:.2f}")

    def _live_execute(self, signal: dict, bet_size: float):
        """Execute real trade on Polymarket."""
        if not self.client:
            print("    [LIVE] No client available")
            return

        market = self.client.find_btc_market()
        if not market:
            print("    [LIVE] No market found")
            return

        side = "YES" if signal["state"] == "UP" else "NO"
        token_id = market["yes_token_id"] if side == "YES" else market["no_token_id"]

        result = self.client.place_market_order(token_id, bet_size, "BUY")

        if result:
            print(f"    [LIVE] Order placed: {result}")
        else:
            print(f"    [LIVE] Order failed")

    def _print_summary(self):
        """Print session summary."""
        summary = self.journal.get_today_summary()
        print(f"\n{'='*50}")
        print(f"  SESSION SUMMARY")
        print(f"  Signals: {summary['signals_detected']}")
        print(f"  Trades: {summary['trades_entered']}")
        print(f"  Win Rate: {summary['win_rate']:.1%}")
        print(f"  P/L: ${summary['total_pnl']:+.2f}")
        print(f"  Bankroll: ${self.bankroll:.2f}")
        print(f"{'='*50}\n")
        self.telegram.notify_daily_summary(summary)
