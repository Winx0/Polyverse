"""
Telegram notification system for trade alerts and daily summaries.
"""

import requests
from datetime import datetime


class TelegramNotifier:
    """
    Sends trading notifications via Telegram bot.
    Messages include: trade entries, exits, daily summaries, errors.
    """

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str, chat_id: str):
        """
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Your Telegram chat ID (use @userinfobot to find)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

    def send(self, message: str) -> bool:
        """Send a message via Telegram."""
        if not self.enabled:
            print(f"[TG-DISABLED] {message}")
            return False

        try:
            url = self.API_URL.format(token=self.bot_token)
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"[TG-ERROR] {e}")
            return False

    def notify_trade_entry(self, side: str, price: float, bet_size: float,
                           persistence: float, edge: float):
        """Notify about a new trade entry."""
        msg = (
            f"🟢 *TRADE ENTRY*\n"
            f"Side: {side}\n"
            f"Price: {price:.4f}\n"
            f"Bet: ${bet_size:.2f}\n"
            f"Persistence: {persistence:.2%}\n"
            f"Edge: {edge:.2%}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(msg)

    def notify_trade_exit(self, outcome: str, pnl: float, bankroll: float):
        """Notify about a trade resolution."""
        emoji = "✅" if outcome == "WIN" else "❌"
        msg = (
            f"{emoji} *TRADE {outcome}*\n"
            f"P/L: ${pnl:+.2f}\n"
            f"Bankroll: ${bankroll:.2f}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(msg)

    def notify_daily_summary(self, summary: dict):
        """Send daily summary report."""
        msg = (
            f"📊 *DAILY SUMMARY* - {summary['date']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Signals: {summary['signals_detected']}\n"
            f"Trades: {summary['trades_entered']}\n"
            f"Resolved: {summary['trades_resolved']}\n"
            f"Win Rate: {summary['win_rate']:.1%}\n"
            f"P/L: ${summary['total_pnl']:+.2f}\n"
            f"Avg/Trade: ${summary['avg_pnl_per_trade']:+.4f}"
        )
        self.send(msg)

    def notify_error(self, error: str):
        """Send error notification."""
        msg = f"⚠️ *ERROR*\n{error}"
        self.send(msg)

    def notify_startup(self, bankroll: float, mode: str):
        """Send bot startup notification."""
        msg = (
            f"🤖 *BOT STARTED*\n"
            f"Mode: {mode}\n"
            f"Bankroll: ${bankroll:.2f}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send(msg)
