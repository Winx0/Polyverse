"""
Entry point for the Polymarket BTC Up/Down Trading Bot.
Run this from the project root: python -m bot.main
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env.bot"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

# Apply proxy from .env if set (for geoblock bypass)
proxy = os.getenv("PROXY_URL", "").strip()
if proxy:
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy
    os.environ["ALL_PROXY"] = proxy
    print(f"[PROXY] Routing through: {proxy.split('@')[-1] if '@' in proxy else proxy}")

from bot.engine import TradingEngine


def load_config() -> dict:
    """Load configuration from environment variables."""
    config = {
        # Trading parameters
        "DRY_RUN": os.getenv("DRY_RUN", "true").lower() == "true",
        "MIN_EDGE": float(os.getenv("MIN_EDGE", "0.05")),
        "MIN_PROB": float(os.getenv("MIN_PROB", "0.87")),
        "MIN_BET": float(os.getenv("MIN_BET", "1.00")),
        "MAX_BET": float(os.getenv("MAX_BET", "2.00")),
        "BANKROLL": float(os.getenv("BANKROLL", "2.00")),
        "LOOP_INTERVAL": int(os.getenv("LOOP_INTERVAL", "81")),

        # Polymarket credentials
        "PRIVATE_KEY": os.getenv("PRIVATE_KEY", ""),
        "SAFE_ADDRESS": os.getenv("SAFE_ADDRESS", ""),
        "CLOB_API_KEY": os.getenv("CLOB_API_KEY", ""),
        "CLOB_API_SECRET": os.getenv("CLOB_API_SECRET", ""),
        "CLOB_API_PASSPHRASE": os.getenv("CLOB_API_PASSPHRASE", ""),

        # Telegram notifications
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
    }
    return config


def main():
    """Main entry point."""
    print("\n" + "=" * 50)
    print("  POLYMARKET BTC UP/DOWN TRADING BOT")
    print("  Markov Chain + Kelly Criterion")
    print("  Modal: $2 | Target: $10,000")
    print("=" * 50 + "\n")

    config = load_config()

    # Safety check
    if not config["DRY_RUN"]:
        if not config["PRIVATE_KEY"]:
            print("[ERROR] PRIVATE_KEY required for live trading!")
            print("[INFO] Set DRY_RUN=true for simulation mode.")
            sys.exit(1)

        print("!!! LIVE TRADING MODE !!!")
        print(f"    Bankroll: ${config['BANKROLL']:.2f}")
        print(f"    Max Bet: ${config['MAX_BET']:.2f}")
        confirm = input("    Type 'YES' to confirm: ")
        if confirm != "YES":
            print("    Aborted.")
            sys.exit(0)

    # Start engine
    engine = TradingEngine(config)
    engine.start()


if __name__ == "__main__":
    main()
