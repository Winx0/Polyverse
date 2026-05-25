#!/bin/bash
# Run Polymarket BTC bot on VPS Linux
# Usage: bash run.sh

set -e

cd "$(dirname "$0")"

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set proxy from .env.bot if PROXY_URL is set
if [ -f .env.bot ]; then
    PROXY_URL=$(grep -E '^PROXY_URL=' .env.bot | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    if [ -n "$PROXY_URL" ]; then
        export HTTP_PROXY="$PROXY_URL"
        export HTTPS_PROXY="$PROXY_URL"
        export ALL_PROXY="$PROXY_URL"
        echo "[PROXY] Using: $PROXY_URL"
    else
        echo "[PROXY] No PROXY_URL set in .env.bot — running without proxy"
    fi
fi

# Run bot
PYTHONPATH=. python3 -m bot.main
