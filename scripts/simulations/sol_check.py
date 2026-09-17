#!/usr/bin/env python3
"""Solana Wallet Balance Checker — read-only, no API key needed.

Uses shared rpc.py for Solana RPC calls.
"""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 2)[0])
from rpc import sol_balance


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sol_check.py <address>")
        sys.exit(1)
    address = sys.argv[1]
    result = sol_balance(address)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
