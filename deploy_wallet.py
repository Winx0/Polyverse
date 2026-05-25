"""
Polymarket Wallet Setup Script (EOA Mode)
- Registers wallet directly without Smart Wallet deployment
- Generates CLOB API credentials
- Approves required contracts
- Saves everything to .env.bot

Run: python deploy_wallet.py
"""

import os
import sys
import json
import time
import getpass
import requests
from pathlib import Path

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
except ImportError:
    print("[ERROR] eth-account not installed!")
    print("Run: pip install eth-account")
    sys.exit(1)

try:
    from web3 import Web3
except ImportError:
    print("[ERROR] web3 not installed!")
    print("Run: pip install web3")
    sys.exit(1)


CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

# Polymarket contract addresses on Polygon
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Standard ERC20 approve ABI
ERC20_ABI = json.loads('[{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"}]')

# Max uint256 for unlimited approval
MAX_UINT256 = 2**256 - 1

# Polygon RPC endpoints (many fallbacks)
RPC_URLS = [
    "https://polygon.drpc.org",
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon.meowrpc.com",
    "https://1rpc.io/matic",
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com",
    "https://rpc-mainnet.matic.quiknode.pro",
    "https://polygon.blockpi.network/v1/rpc/public",
    "https://polygon-mainnet.public.blastapi.io",
    "https://api.zan.top/node/v1/polygon/mainnet/public",
    "https://polygon.gateway.tenderly.co",
]


def get_web3():
    """Connect to Polygon network."""
    for rpc in RPC_URLS:
        try:
            print(f"       Trying {rpc}...", end=" ")
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 8}))
            if w3.is_connected():
                print("OK!")
                return w3
            else:
                print("failed")
        except Exception:
            print("timeout")
            continue
    print("\n[ERROR] Cannot connect to Polygon network!")
    print("[TIP]  Your network may be blocking crypto RPCs.")
    print("       Try using a VPN, or mobile hotspot.")
    sys.exit(1)


def derive_api_key(private_key: str, address: str) -> dict:
    """
    Derive API key from Polymarket CLOB.
    Uses the create-api-key endpoint with HMAC auth.
    """
    # Method 1: Try py_clob_client if available
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON

        client = ClobClient(
            host=CLOB_HOST,
            chain_id=POLYGON,
            key=private_key,
        )
        creds = client.derive_api_key()
        return {
            "api_key": creds.api_key,
            "api_secret": creds.api_secret,
            "api_passphrase": creds.api_passphrase,
        }
    except Exception as e1:
        print(f"[INFO] py_clob_client method failed: {e1}")

    # Method 2: Direct API call
    try:
        timestamp = int(time.time())
        nonce = 0

        # Create the signing message for Polymarket
        msg_to_sign = f"Login to Polymarket"
        message = encode_defunct(text=msg_to_sign)
        account = Account.from_key(private_key)
        signed = account.sign_message(message)

        # Try to create API key via REST
        url = f"{CLOB_HOST}/auth/api-key"
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "address": address,
            "signature": signed.signature.hex(),
            "message": msg_to_sign,
            "timestamp": str(timestamp),
            "nonce": str(nonce),
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return {
                "api_key": data.get("apiKey", ""),
                "api_secret": data.get("secret", ""),
                "api_passphrase": data.get("passphrase", ""),
            }
        else:
            print(f"[INFO] API key endpoint returned: {response.status_code}")
            print(f"       Response: {response.text[:200]}")
    except Exception as e2:
        print(f"[INFO] Direct API method failed: {e2}")

    return None


def approve_contracts(w3, private_key: str, address: str):
    """Approve USDC spending for Polymarket contracts."""
    account = Account.from_key(private_key)
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)

    contracts_to_approve = [
        ("CTF Exchange", CTF_EXCHANGE),
        ("Neg Risk CTF Exchange", NEG_RISK_CTF_EXCHANGE),
        ("Neg Risk Adapter", NEG_RISK_ADAPTER),
    ]

    for name, contract_addr in contracts_to_approve:
        try:
            nonce = w3.eth.get_transaction_count(address)
            gas_price = w3.eth.gas_price

            tx = usdc.functions.approve(
                Web3.to_checksum_address(contract_addr),
                MAX_UINT256
            ).build_transaction({
                "from": address,
                "nonce": nonce,
                "gasPrice": gas_price,
                "gas": 60000,
                "chainId": 137,
            })

            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"[OK] {name} approved! TX: {tx_hash.hex()[:20]}...")

            # Wait for confirmation
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        except Exception as e:
            error_msg = str(e)
            if "insufficient funds" in error_msg.lower():
                print(f"[ERROR] {name}: Not enough POL for gas!")
                print(f"        Send 0.1 POL to {address}")
                return False
            else:
                print(f"[WARN] {name}: {e}")

    return True


def main():
    print("\n" + "=" * 50)
    print("  POLYMARKET WALLET SETUP (EOA Mode)")
    print("  No Smart Wallet needed!")
    print("=" * 50 + "\n")

    # Get private key securely
    print("[INPUT] Paste your wallet PRIVATE KEY below.")
    print("        (Input is hidden - won't show on screen)\n")

    private_key = getpass.getpass("Private Key (0x...): ").strip()

    if not private_key:
        print("[ERROR] No private key provided!")
        sys.exit(1)

    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    # Validate key
    try:
        account = Account.from_key(private_key)
        address = account.address
        print(f"\n[OK] Wallet address: {address}")
    except Exception as e:
        print(f"[ERROR] Invalid private key: {e}")
        sys.exit(1)

    # Connect to Polygon
    print("\n[1/4] Connecting to Polygon network...")
    w3 = get_web3()

    # Check POL balance
    balance = w3.eth.get_balance(address)
    pol_balance = w3.from_wei(balance, "ether")
    print(f"[INFO] POL balance: {pol_balance:.4f} POL")

    if pol_balance < 0.01:
        print(f"\n[WARNING] Very low POL balance!")
        print(f"         You need ~0.05 POL for contract approvals.")
        print(f"         Send POL to: {address}")
        cont = input("\n         Continue anyway? (y/n): ").strip().lower()
        if cont != "y":
            sys.exit(0)

    # Approve contracts
    print("\n[2/4] Approving Polymarket contracts...")
    if pol_balance >= 0.01:
        success = approve_contracts(w3, private_key, address)
        if success:
            print("[OK] All contracts approved!")
        else:
            print("[WARN] Some approvals may have failed.")
    else:
        print("[SKIP] Not enough POL for approvals. Will try later.")

    # Generate API credentials
    print("\n[3/4] Generating API credentials...")
    api_creds = derive_api_key(private_key, address)

    if api_creds and api_creds.get("api_key"):
        print(f"[OK] API Key: {api_creds['api_key'][:10]}...")
    else:
        print("[WARN] Could not generate API key automatically.")
        print("[INFO] Bot will use signature-based auth instead.")
        api_creds = {"api_key": "", "api_secret": "", "api_passphrase": ""}

    # Save to .env.bot
    print("\n[4/4] Saving to .env.bot...")

    env_content = f"""# ============================================
# POLYMARKET BTC UP/DOWN TRADING BOT CONFIG
# Generated by deploy_wallet.py
# ============================================

# --- TRADING MODE ---
DRY_RUN=true
BANKROLL=2.00

# --- STRATEGY PARAMETERS ---
MIN_EDGE=0.05
MIN_PROB=0.87
MIN_BET=0.25
MAX_BET=1.00
LOOP_INTERVAL=81

# --- POLYMARKET WALLET ---
PRIVATE_KEY={private_key}
SAFE_ADDRESS={address}

# --- API CREDENTIALS ---
CLOB_API_KEY={api_creds['api_key']}
CLOB_API_SECRET={api_creds['api_secret']}
CLOB_API_PASSPHRASE={api_creds['api_passphrase']}

# --- TELEGRAM (optional) ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
"""

    env_path = Path(__file__).parent / ".env.bot"
    with open(env_path, "w") as f:
        f.write(env_content)

    print(f"[OK] Saved to: {env_path}")

    # Summary
    print("\n" + "=" * 50)
    print("  SETUP COMPLETE!")
    print("=" * 50)
    print(f"\n  Wallet:     {address}")
    print(f"  POL:        {pol_balance:.4f}")
    print(f"  API Key:    {'YES' if api_creds.get('api_key') else 'NO (will use sig auth)'}")
    print(f"  Approvals:  {'DONE' if pol_balance >= 0.01 else 'PENDING (need POL)'}")
    print(f"  Mode:       DRY_RUN=true (safe start)")
    print(f"\n  Next steps:")
    print(f"  1. Deposit USDC to {address} on Polygon")
    print(f"  2. Run: .\\run.ps1  (DRY RUN test first)")
    print(f"  3. Edit .env.bot → DRY_RUN=false for live")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
