"""RPC — shared blockchain RPC helpers with failover.

Single source of truth for ETH and Solana RPC calls.
Every on-chain tool imports from here instead of duplicating.
"""
from __future__ import annotations

import json
import urllib.request

# ── ETH / EVM RPCs (free, no key) ─────────────────────────────────────

ETH_RPCS = [
    "https://rpc.ankr.com/eth",
    "https://eth.llamarpc.com",
    "https://ethereum-rpc.publicnode.com",
    "https://1rpc.io/eth",
]

ERC20_TOKENS = {
    "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
    "USDT": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
    "DAI": ("0x6B175474E89094C44Da98b954EedeAC495271d0F", 18),
}


def eth_rpc(method: str, params: list, rpcs: list[str] | None = None) -> dict:
    """Call an ETH JSON-RPC endpoint with failover across multiple RPCs."""
    rpcs = rpcs or ETH_RPCS
    last_err = None
    for rpc in rpcs:
        try:
            body = json.dumps({
                "jsonrpc": "2.0", "id": 1,
                "method": method, "params": params,
            }).encode()
            req = urllib.request.Request(
                rpc, data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            continue
    raise last_err or Exception("all ETH RPCs failed")


def eth_balance(address: str) -> dict:
    """Check ETH balance + major ERC-20 tokens."""
    result = {}
    resp = eth_rpc("eth_getBalance", [address, "latest"])
    wei = int(resp.get("result", "0x0"), 16)
    eth = wei / 1e18
    result["ETH"] = round(eth, 6)
    result["eth_usd"] = round(eth * 2500, 2)

    for name, (contract, decimals) in ERC20_TOKENS.items():
        try:
            data = "0x70a08231" + address[2:].lower().zfill(64)
            resp = eth_rpc("eth_call", [{"to": contract, "data": data}, "latest"])
            raw = int(resp.get("result", "0x0"), 16)
            amount = raw / (10 ** decimals)
            result[name] = round(amount, 6)
            result[f"{name.lower()}_usd"] = round(amount, 2)
        except Exception:
            result[name] = 0
            result[f"{name.lower()}_usd"] = 0

    result["total_usd"] = round(
        sum(v for k, v in result.items() if k.endswith("_usd")), 2
    )
    return result


# ── Solana RPCs (free, no key) ────────────────────────────────────────

SOL_RPC = "https://api.mainnet-beta.solana.com"


def sol_rpc(method: str, params: list | None = None) -> dict:
    """Call Solana JSON-RPC."""
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": method, "params": params or [],
    }).encode()
    req = urllib.request.Request(
        SOL_RPC, data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def sol_balance(address: str) -> dict:
    """Check SOL balance + SPL tokens."""
    result = {}
    resp = sol_rpc("getBalance", [address])
    lamports = resp.get("result", {}).get("value", 0)
    sol = lamports / 1e9
    result["SOL"] = round(sol, 6)
    result["sol_usd"] = round(sol * 150, 2)

    resp = sol_rpc("getTokenAccountsByOwner", [
        address,
        {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
        {"encoding": "jsonParsed"},
    ])
    tokens = {}
    for acc in resp.get("result", {}).get("value", []):
        info = acc["account"]["data"]["parsed"]["info"]
        mint = info["mint"]
        amount = info["tokenAmount"]["uiAmount"] or 0
        if amount > 0:
            tokens[mint] = amount
    result["spl_tokens"] = tokens
    result["spl_count"] = len(tokens)
    return result
