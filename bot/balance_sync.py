"""
On-chain balance sync for Polymarket V2 deposit wallet.
Queries pUSD balance via Polygon RPC.
"""

import requests

PUSD_CONTRACT = "0xb24cd494faE4C180A89975F1328Eab2a7D5d8f11"
POLYGON_RPC = "https://polygon.drpc.org"


def get_pusd_balance(wallet_address: str) -> float:
    """Get pUSD balance for a wallet via on-chain RPC call."""
    if not wallet_address:
        return 0.0
    try:
        # ERC20 balanceOf(address) selector
        data = "0x70a08231" + wallet_address.lower().replace("0x", "").zfill(64)
        response = requests.post(
            POLYGON_RPC,
            json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": PUSD_CONTRACT, "data": data}, "latest"],
                "id": 1,
            },
            timeout=8,
        )
        if response.status_code == 200:
            result = response.json().get("result", "0x0")
            if result and result != "0x0":
                return int(result, 16) / 1e6  # pUSD has 6 decimals
    except Exception as e:
        print(f"[BALANCE] Sync error: {str(e)[:80]}")
    return 0.0
