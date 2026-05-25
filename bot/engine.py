"""
Main trading engine - orchestrates all components.
Runs the trading loop: fetch data -> analyze -> decide -> execute.
Includes Flask mini server for live dashboard at http://localhost:5000/state
"""

import os
import time
import json
from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, jsonify, send_from_directory

from bot.markov import MarkovModel
from bot.kelly import KellySizer
from bot.price_feed import BTCPriceFeed
from bot.polymarket_client import PolymarketClient
from bot.journal import TradeJournal
from bot.telegram_notifier import TelegramNotifier
from bot.balance_sync import get_account_balance, get_collateral_balance

# --- Flask Dashboard Server ---
flask_app = Flask(__name__)
bot_state = {}

@flask_app.route('/state')
def get_state():
    return jsonify(bot_state)

@flask_app.route('/')
def index():
    return send_from_directory(str(Path(__file__).parent), 'dashboard.html')

def _run_flask():
    flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# Start Flask in background thread
Thread(target=_run_flask, daemon=True).start()


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
        # Use smaller window for faster adaptation to current trend
        self.markov = MarkovModel(window_size=20)
        self.kelly = KellySizer(
            max_fraction=0.50,
            min_bet=config.get("MIN_BET", 1.00),
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
                    api_key=config.get("CLOB_API_KEY", ""),
                    api_secret=config.get("CLOB_API_SECRET", ""),
                    api_passphrase=config.get("CLOB_API_PASSPHRASE", ""),
                )

        self.running = False
        self.trades_today = 0
        self.signals_today = 0
        self.wins = 0
        self.losses = 0
        self.skips = 0
        self.resolved_list = []
        # Track 5-minute windows for proper Markov updates
        self.last_window_ts = 0
        self.window_start_price = None
        # Posisi live yang belum di-settle, di-key per window_ts.
        # Tiap entry: list of dict {side, shares, paid, p, edge, order_id, ...}
        # Saat window resolve, semua posisi di window itu di-settle (WIN/LOSS).
        self.open_positions: dict[int, list[dict]] = {}
        # File untuk persist open_positions supaya gak hilang saat bot restart.
        self._positions_file = Path("data/open_positions.json")

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
            else:
                # Auto-sync bankroll dari CLOB collateral.
                # Mengabaikan BANKROLL di .env karena bisa stale (saldo udah
                # berubah sejak file ditulis terakhir kali). CLOB selalu
                # real-time. Fallback: kalau query gagal, pakai .env.
                try:
                    coll = get_collateral_balance(self.client)
                    if coll is not None and coll > 0:
                        old = self.bankroll
                        self.bankroll = coll
                        print(
                            f"[ENGINE] Bankroll auto-synced from CLOB: "
                            f"${old:.2f} -> ${coll:.2f}"
                        )
                    elif coll == 0:
                        print(
                            f"[ENGINE] CLOB collateral=0. Pakai bankroll dari "
                            f".env: ${self.bankroll:.2f}"
                        )
                    else:
                        print(
                            f"[ENGINE] CLOB query gagal. Pakai bankroll dari "
                            f".env: ${self.bankroll:.2f}"
                        )
                except Exception as e:
                    print(f"[ENGINE] Bankroll sync error: {e}")

        # Load open_positions yang ke-save dari session sebelumnya.
        # Posisi yang window-nya udah lewat akan ditandai late_at_load=True
        # supaya pas settle gak double-credit bankroll (CLOB udah include payout).
        self._load_open_positions()

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
        # 1. Get latest price
        current_price = self.price_feed.get_current_price()
        if current_price is None:
            return

        # 2. Track 5-minute windows for Markov model
        # Each window = 300 seconds. When a new window starts,
        # resolve the previous one as UP or DOWN.
        current_ts = int(time.time())
        current_window = (current_ts // 300) * 300

        if self.last_window_ts == 0:
            # First tick - initialize
            self.last_window_ts = current_window
            self.window_start_price = current_price
            return

        if current_window > self.last_window_ts:
            # New 5-minute window started! Resolve the previous window.
            if self.window_start_price is not None:
                if current_price >= self.window_start_price:
                    resolved_state = "UP"
                else:
                    resolved_state = "DOWN"

                # Update Markov model with resolved window
                self.markov.add_observation(resolved_state)
                self.resolved_list.append({
                    "state": resolved_state,
                    "time": datetime.now().strftime("%H:%M:%S"),
                })
                # Keep last 20 resolved
                if len(self.resolved_list) > 20:
                    self.resolved_list = self.resolved_list[-20:]
                matrix = self.markov.get_transition_matrix()
                print(f"    [WINDOW] Resolved: {resolved_state} | "
                      f"P(UP|UP)={matrix['P(UP|UP)']:.3f} "
                      f"P(DN|DN)={matrix['P(DOWN|DOWN)']:.3f} "
                      f"(history={len(self.markov.history)})")

                # Settle posisi live yang taruhannya di window ini.
                # Harus dipanggil SETELAH Markov diupdate (biar urutan log rapi)
                # dan SEBELUM last_window_ts diganti (biar match key).
                self._settle_window(
                    window_ts=self.last_window_ts,
                    resolved_state=resolved_state,
                    start_price=self.window_start_price,
                    end_price=current_price,
                )

            # Reset for new window
            self.last_window_ts = current_window
            self.window_start_price = current_price

        # 3. Check if we have enough data
        if not self.markov.has_enough_data():
            return

        # 4. Get persistence probability for current state
        current_state = self.markov.get_current_state()
        persistence = self.markov.get_persistence_probability(current_state)

        # 5. Check entry conditions
        signal = self._evaluate_signal(current_state, persistence)
        self.signals_today += 1

        if signal["action"] == "ENTER":
            self._execute_trade(signal)
        else:
            self.skips += 1

    def _evaluate_signal(self, state: str, persistence: float) -> dict:
        """Evaluate whether to enter a trade."""
        # Simulate market price (in dry run) or fetch real
        market_price = 0.50  # Default
        market_name = ""

        if self.client and not self.dry_run:
            market = self.client.find_btc_market()
            if market:
                side = "YES" if state == "UP" else "NO"
                market_price = self.client.get_market_price(market, side)
                market_name = market.get("question", "")
        else:
            # In dry run, simulate market price based on persistence
            # Market usually prices between 0.45-0.65
            import random
            market_price = 0.45 + random.random() * 0.20
            market_name = "DRY RUN (simulated)"

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
            "market_name": market_name,
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

        # Update dashboard state
        self._update_bot_state(signal)

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
        if won:
            self.wins += 1
        else:
            self.losses += 1

    def _live_execute(self, signal: dict, bet_size: float):
        """
        Execute real trade on Polymarket V2 deposit wallet.

        Catatan penting: di mode LIVE, exit TIDAK di-log di sini.
        Posisi disimpan ke `self.open_positions[window_ts]` dan baru di-settle
        saat window 5-menit resolve (lihat `_settle_window`). Ini fix bug lama
        di mana wins/losses gak pernah ke-counter dan bankroll gak di-credit
        saat menang.
        """
        if not self.client:
            print("    [LIVE] No client available")
            return

        market = self.client.find_btc_market()
        if not market:
            print("    [LIVE] No market found")
            return

        # We always BUY a YES token: if state=UP we buy UP token, if DOWN we buy DOWN token
        side = "BUY"
        token_id = market["yes_token_id"] if signal["state"] == "UP" else market["no_token_id"]

        # Polymarket V2 minimum order is ~$1.00 USD (5 shares @ $0.20 minimum).
        # bet_size is already in USD.
        if bet_size < 1.0:
            print(f"    [LIVE] bet_size ${bet_size:.2f} < $1 minimum, skipping")
            return

        result = self.client.place_market_order(token_id, bet_size, side)

        if result and isinstance(result, dict) and result.get("success"):
            taking = float(result.get("takingAmount", 0))  # shares received
            making = float(result.get("makingAmount", 0))  # USD paid
            print(f"    [LIVE] FILLED ✓ paid ${making:.4f} → got {taking:.4f} shares")

            # Debit bankroll segera (USD keluar dari akun saat order matched).
            # Credit (kalau menang) akan dilakukan di _settle_window.
            self.bankroll -= making

            side_yn = "YES" if signal["state"] == "UP" else "NO"
            order_id = result.get("orderID", "") or result.get("order_id", "")
            tx_hash = ""
            tx_list = result.get("transactionsHashes", []) or result.get("transaction_hashes", [])
            if tx_list:
                tx_hash = tx_list[0]

            position = {
                "side": side_yn,
                "shares": taking,
                "paid": making,
                "token_id": token_id,
                "condition_id": market.get("condition_id", ""),
                "slug": market.get("slug", ""),
                "entry_price": signal["market_price"],
                "p": signal["persistence_prob"],
                "edge": signal["edge"],
                "order_id": order_id,
                "tx_hash": tx_hash,
                "market": signal.get("market_name", ""),
                "entry_time": datetime.now().isoformat(),
            }
            # Simpan posisi di window saat ini. Window ini akan resolve
            # saat current_ts melewati (last_window_ts + 300).
            self.open_positions.setdefault(self.last_window_ts, []).append(position)
            # Persist supaya gak hilang kalau bot restart sebelum settle.
            self._save_open_positions()

            # Log fill (bukan exit) — exit di-log nanti pas settle.
            self.journal.log_trade_fill({
                "window_ts": self.last_window_ts,
                "side": side_yn,
                "shares": taking,
                "paid": making,
                "order_id": order_id,
                "tx_hash": tx_hash,
                "bankroll_after_entry": round(self.bankroll, 4),
            })
        else:
            print(f"    [LIVE] Order failed: {result}")

    def _save_open_positions(self):
        """
        Persist open_positions ke disk supaya bot bisa recover setelah restart.

        Format JSON: {"<window_ts>": [{...pos...}, ...]}
        Atomic write (tulis ke .tmp dulu, lalu rename) biar gak corrupt
        kalau kena interrupt di tengah write.
        """
        try:
            self._positions_file.parent.mkdir(parents=True, exist_ok=True)
            # Convert int keys -> str (JSON requirement)
            data = {str(k): v for k, v in self.open_positions.items()}
            tmp = self._positions_file.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, default=str)
            tmp.replace(self._positions_file)
        except Exception as e:
            print(f"[POSITIONS] Save gagal: {e}")

    def _load_open_positions(self):
        """
        Load open_positions dari disk pas startup.

        Posisi yang window-nya udah lewat (current_ts > window_ts + 300)
        ditandai `late_at_load=True`. Ini penting karena:
            - Bankroll diinit dari CLOB collateral yang udah include hasil resolve
            - Kalau kita credit bankroll lagi pas settle -> double counting
            - Solusi: untuk posisi late_at_load, settle tetap jalan tapi
              cuma update wins/losses/journal, tidak modify bankroll.
        """
        if not self._positions_file.exists():
            return

        try:
            with open(self._positions_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[POSITIONS] Load gagal (file rusak?): {e}")
            return

        now = time.time()
        loaded = 0
        late = 0

        for window_ts_str, positions in data.items():
            try:
                window_ts = int(window_ts_str)
            except ValueError:
                continue

            for pos in positions:
                if now > window_ts + 300:
                    pos["late_at_load"] = True
                    late += 1
            self.open_positions.setdefault(window_ts, []).extend(positions)
            loaded += len(positions)

        if loaded:
            print(
                f"[POSITIONS] Loaded {loaded} posisi dari disk "
                f"({late} udah lewat window, akan settle late)"
            )

    def _settle_window(
        self,
        window_ts: int,
        resolved_state: str,
        start_price: float,
        end_price: float,
    ):
        """
        Settle semua posisi live yang taruhannya di window `window_ts`.

        Logic:
            - YES (taruhan UP) menang kalau resolved_state == "UP"
            - NO  (taruhan DOWN) menang kalau resolved_state == "DOWN"
            - Win  -> payout = shares * $1.00, credit ke bankroll
            - Loss -> payout = $0 (paid sudah di-debit di entry, gak diapa-apain)

        Update yang dilakukan per posisi:
            - self.wins / self.losses counter
            - self.bankroll (credit kalau menang)
            - Journal exit (JSON event log + CSV row)
            - Telegram notify

        Catatan: arah BTC pakai harga lokal (Kraken/CoinGecko/Coinbase). Kita
        coba CROSS-CHECK ke Polymarket gamma API (oracle resmi) — kalau
        berhasil, hasil oracle yang dipakai. Kalau market belum closed di
        Polymarket atau query gagal, fallback ke harga lokal.

        Posisi dengan flag `late_at_load=True` (di-load dari disk pas startup,
        dan window-nya udah lewat saat itu) tetap di-settle untuk update
        statistik & journal, TAPI bankroll TIDAK dimodifikasi karena CLOB
        collateral pas startup udah include hasil resolve.
        """
        positions = self.open_positions.pop(window_ts, [])
        if not positions:
            return

        # Setelah pop, simpan state baru ke disk
        self._save_open_positions()

        # Cross-check ke Polymarket oracle (sumber truth lebih akurat
        # daripada price feed lokal). Pakai condition_id dari posisi pertama
        # (semua posisi di 1 window pasti di market yang sama).
        local_state = resolved_state
        oracle_state: str | None = None
        if self.client and not self.dry_run:
            cid = positions[0].get("condition_id", "")
            slug = positions[0].get("slug", "")
            if cid or slug:
                oracle_state = self.client.get_market_resolution(
                    condition_id=cid, slug=slug
                )

        if oracle_state and oracle_state != local_state:
            print(
                f"    [ORACLE] Polymarket resolve: {oracle_state} | "
                f"lokal bilang: {local_state} | pakai oracle ✓"
            )
            resolved_state = oracle_state
        elif oracle_state:
            # match — confidence boost, gak perlu print
            pass
        elif self.client and not self.dry_run:
            print(
                f"    [ORACLE] belum resolve / query gagal, fallback ke "
                f"harga lokal ({local_state})"
            )

        for pos in positions:
            side = pos["side"]
            shares = pos["shares"]
            paid = pos["paid"]
            is_late = pos.get("late_at_load", False)

            won = (
                (side == "YES" and resolved_state == "UP")
                or (side == "NO" and resolved_state == "DOWN")
            )

            if won:
                payout = shares * 1.0  # tiap winning share = $1.00
                pnl = payout - paid
                # Hanya credit bankroll kalau posisi ini ENTRY dalam session
                # ini (bukan posisi yang di-load dari disk dan udah ke-resolve
                # di Polymarket — bankroll udah include payout via CLOB init).
                if not is_late:
                    self.bankroll += payout
                self.wins += 1
                outcome = "WIN"
            else:
                payout = 0.0
                pnl = -paid
                # Loss: paid sudah ke-debit di entry (atau, kalau is_late,
                # paid sudah ke-debit langsung di Polymarket dan reflected
                # di CLOB pas init). Either way, bankroll gak diapa-apain.
                self.losses += 1
                outcome = "LOSS"

            now_iso = datetime.now().isoformat()

            # 1. Log ke event JSON (detail lengkap, untuk replay/debugging)
            exit_record = {
                "outcome": outcome,
                "pnl": round(pnl, 4),
                "bankroll_after": round(self.bankroll, 4),
                "side": side,
                "shares": round(shares, 4),
                "paid": round(paid, 4),
                "payout": round(payout, 4),
                "resolved_state": resolved_state,
                "resolved_by": "oracle" if oracle_state else "local",
                "late_at_load": is_late,
                "start_price": round(start_price, 2),
                "end_price": round(end_price, 2),
                "window_ts": window_ts,
                "p": round(pos.get("p", 0), 4),
                "edge": round(pos.get("edge", 0), 4),
                "order_id": pos.get("order_id", ""),
                "tx_hash": pos.get("tx_hash", ""),
                "market": pos.get("market", ""),
            }
            self.journal.log_trade_exit(exit_record)

            # 2. Log ke CSV flat (1 row per trade resolved, untuk analisis)
            self.journal.log_csv_trade({
                "timestamp": now_iso,
                **exit_record,
            })

            # 3. Telegram notify (akan no-op kalau token kosong)
            try:
                self.telegram.notify_trade_exit(outcome, pnl, self.bankroll)
            except Exception as e:
                print(f"    [SETTLE] Telegram notify gagal: {e}")

            # 4. Console summary
            emoji = "🟢 WIN " if won else "🔴 LOSS"
            late_tag = " [LATE]" if is_late else ""
            print(
                f"    <<< {emoji} {side}{late_tag} | shares={shares:.2f} "
                f"paid=${paid:.2f} payout=${payout:.2f} "
                f"P/L=${pnl:+.4f} | Bankroll: ${self.bankroll:.2f}"
            )

    def _update_bot_state(self, signal: dict):
        """Update global bot_state for Flask dashboard and write to file."""
        global bot_state
        matrix = self.markov.get_transition_matrix()

        # Sync balance dari Polymarket setiap 30 detik (mode live aja).
        # CATATAN PENTING: bankroll internal (self.bankroll) sekarang TIDAK
        # di-overwrite dari sini. Internal counter = source of truth karena:
        #   - Selalu real-time (debit di entry, credit di settle)
        #   - Tidak terganggu lag on-chain settlement
        # Balance dari API hanya buat ditampilkan di dashboard sebagai cross-check.
        onchain_bal = 0.0
        total_value = 0.0
        bal_source = "n/a"

        if not self.dry_run:
            now = time.time()
            if now - getattr(self, "_last_balance_sync", 0) > 30:
                bal = get_account_balance(
                    client=self.client,
                    wallet_address=self.config.get("SAFE_ADDRESS", ""),
                )
                self._last_balance_sync = now
                self._cached_balance = bal
            else:
                bal = getattr(self, "_cached_balance", None) or {
                    "collateral": None,
                    "total_value": None,
                    "source": "n/a",
                }

            onchain_bal = bal.get("collateral") or 0.0
            total_value = bal.get("total_value") or 0.0
            bal_source = bal.get("source") or "n/a"

        bot_state = {
            "bankroll": round(self.bankroll, 4),
            "onchain_balance": round(onchain_bal, 4),     # USDC liquid (CLOB)
            "total_value": round(total_value, 4),         # USDC + posisi (Data API)
            "balance_source": bal_source,
            "funder": self.config.get("SAFE_ADDRESS", ""),
            "state": signal["state"],
            "p": round(signal["persistence_prob"], 4),
            "q": round(signal["market_price"], 4),
            "edge": round(signal["edge"], 4),
            "action": signal["action"],
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "wins": self.wins,
            "losses": self.losses,
            "skips": self.skips,
            "open_positions": sum(len(v) for v in self.open_positions.values()),
            "p_up_up": round(float(matrix["P(UP|UP)"]), 4),
            "p_dn_dn": round(float(matrix["P(DOWN|DOWN)"]), 4),
            "hist_size": len(self.markov.history),
            "market": signal.get("market_name", ""),
            "resolved": self.resolved_list,
            "mode": "DRY RUN" if self.dry_run else "LIVE",
            "min_prob": self.min_prob,
            "min_edge": self.min_edge,
        }
        # Write to file as backup
        try:
            state_path = Path("data/bot_state.json")
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(bot_state, f, indent=2)
        except Exception:
            pass

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
