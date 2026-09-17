#!/usr/bin/env python3
"""Batch Wallet Checker — check many addresses in parallel.

Reads addresses from a file (one per line) or stdin, checks ETH + SOL
balances via free public RPCs, sorts by value. For CTF triage.
Adapted from stallshark BLUE-TEAM-COMBINED.md.
"""
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ETH_RPC = "https://ethereum-rpc.publicnode.com"
SOL_RPC = "https://api.mainnet-beta.solana.com"


def eth_rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(ETH_RPC, data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def sol_rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(SOL_RPC, data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def check_eth(address):
    try:
        resp = eth_rpc("eth_getBalance", [address, "latest"])
        wei = int(resp.get("result", "0x0"), 16)
        return {"address": address, "chain": "ETH", "balance": wei / 1e18,
                "usd": round(wei / 1e18 * 2500, 2)}
    except Exception:
        return {"address": address, "chain": "ETH", "balance": 0, "usd": 0}


def check_sol(address):
    try:
        resp = sol_rpc("getBalance", [address])
        lamports = resp.get("result", {}).get("value", 0)
        return {"address": address, "chain": "SOL", "balance": lamports / 1e9,
                "usd": round(lamports / 1e9 * 150, 2)}
    except Exception:
        return {"address": address, "chain": "SOL", "balance": 0, "usd": 0}


def detect_chain(address):
    if address.startswith("0x") and len(address) == 42:
        return "eth"
    return "sol"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 batch_check.py <addresses_file>")
        print("  File: one address per line (0x... for ETH, base58 for SOL)")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        addresses = [ln.strip() for ln in f if ln.strip()]

    print(f"Checking {len(addresses)} addresses...", file=sys.stderr)

    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {}
        for addr in addresses:
            chain = detect_chain(addr)
            if chain == "eth":
                futures[pool.submit(check_eth, addr)] = addr
            else:
                futures[pool.submit(check_sol, addr)] = addr

        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda x: -x["usd"])

    funded = [r for r in results if r["usd"] > 0]
    print(json.dumps({
        "total_checked": len(results),
        "funded": len(funded),
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
