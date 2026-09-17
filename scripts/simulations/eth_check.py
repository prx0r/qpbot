#!/usr/bin/env python3
"""ETH/EVM Wallet Balance Checker — read-only, no API key needed.

Uses shared rpc.py for failover across free public RPCs.
"""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 2)[0])
from rpc import eth_balance


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 eth_check.py <address>")
        sys.exit(1)
    address = sys.argv[1]
    result = eth_balance(address)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
