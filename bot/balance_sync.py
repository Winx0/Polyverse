"""
Balance sync for Polymarket V2 deposit wallet.

Sumber data balance (urutan reliability):
    1. CLOB get_balance_allowance() -> liquid USDC collateral di akun Polymarket.
       Ini paling akurat untuk dana yang siap dipakai trading.
    2. Polymarket Data API /value -> total USD value (USDC + nilai posisi aktif).
       Berguna sebagai cross-check, terutama saat ada posisi belum settle.

Catatan:
    Pendekatan lama (raw ERC20 balanceOf via Polygon RPC) DIHAPUS karena
    Polymarket V2 deposit wallet bukan plain EOA - dananya bisa di Safe,
    di CTF Exchange (locked-in-position), atau di vault internal. Query
    on-chain ke 1 contract address sering balikin 0 walaupun saldo ada.
"""

from typing import Optional

import requests

DATA_API = "https://data-api.polymarket.com"


def get_collateral_balance(client) -> Optional[float]:
    """
    Ambil USDC collateral balance via CLOB API.

    Args:
        client: Instance PolymarketClient (yang punya .client = ClobClient V2).

    Returns:
        Saldo dalam USD (float), atau None kalau query gagal.
        None membedakan "query gagal" dari "saldo memang 0".
    """
    if not client or not getattr(client, "client", None):
        return None

    try:
        from py_clob_client_v2.clob_types import (
            BalanceAllowanceParams,
            AssetType,
        )

        params = BalanceAllowanceParams(
            asset_type=AssetType.COLLATERAL,
            signature_type=3,  # POLY_1271 (V2 deposit wallet)
        )
        result = client.client.get_balance_allowance(params)

        # V2 SDK kadang return dict, kadang return object. Handle dua-duanya.
        if isinstance(result, dict):
            balance_raw = result.get("balance", "0")
        else:
            balance_raw = getattr(result, "balance", "0")

        # USDC native = 6 desimal
        return float(balance_raw) / 1e6

    except Exception as e:
        print(f"[BALANCE] CLOB query gagal: {str(e)[:120]}")
        return None


def get_polymarket_value(wallet_address: str, timeout: int = 8) -> Optional[float]:
    """
    Ambil total Polymarket account value (USDC liquid + nilai posisi aktif)
    via Polymarket public Data API.

    Args:
        wallet_address: Address Polymarket profile / deposit wallet.
        timeout: Request timeout (detik).

    Returns:
        Total value dalam USD, atau None kalau query gagal / address tidak terdaftar.
    """
    if not wallet_address:
        return None

    try:
        r = requests.get(
            f"{DATA_API}/value",
            params={"user": wallet_address},
            timeout=timeout,
        )
        if r.status_code != 200:
            return None

        data = r.json()
        if isinstance(data, list) and data:
            return float(data[0].get("value", 0))
    except Exception as e:
        print(f"[BALANCE] Data API gagal: {str(e)[:120]}")

    return None


def get_account_balance(client=None, wallet_address: str = "") -> dict:
    """
    Unified balance reporter. Coba semua sumber dan return ringkasan.

    Returns:
        {
            "collateral":  float | None,  # USDC liquid (siap trading)
            "total_value": float | None,  # USDC + nilai posisi aktif
            "source":      "clob" | "data_api" | "unavailable",
        }
    """
    result = {
        "collateral": None,
        "total_value": None,
        "source": "unavailable",
    }

    coll = get_collateral_balance(client)
    if coll is not None:
        result["collateral"] = coll
        result["source"] = "clob"

    val = get_polymarket_value(wallet_address)
    if val is not None:
        result["total_value"] = val
        if result["source"] == "unavailable":
            result["source"] = "data_api"

    return result


# --- Backward-compat shim ---------------------------------------------------
# Kode lama (engine.py versi lama) mungkin masih import get_pusd_balance.
# Biar gak error kalau ada cabang yang belum diupdate, kita expose alias
# yang return 0.0 (silent no-op) supaya gak nyangkut di startup.
def get_pusd_balance(wallet_address: str) -> float:  # pragma: no cover
    """DEPRECATED: dipertahankan hanya untuk backward compat. Jangan dipakai."""
    return 0.0
