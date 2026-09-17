#!/usr/bin/env python3
"""Vault Secret Classifier — detect key type and assign tier.

Reads a secret value and classifies it as solana_key, eth_key, mnemonic,
api_key, password, etc. For CTF prize system integration.
Adapted from qpbot/agentcom/vault/classifier.py patterns.
"""
import re
import sys

ETH_KEY = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")
MNEMONIC_12 = re.compile(r"^([a-z]+\s+){11}[a-z]+$")
MNEMONIC_24 = re.compile(r"^([a-z]+\s+){23}[a-z]+$")
AWS_KEY = re.compile(r"^AKIA[0-9A-Z]{16}$")
OPENAI_KEY = re.compile(r"^sk-[A-Za-z0-9-]{20,}$")
GH_TOKEN = re.compile(r"^ghp_[A-Za-z0-9]{36}$")
SLACK_TOKEN = re.compile(r"^xox[bpsar]-[A-Za-z0-9-]{10,}$")
SOL_KEY = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64}$")
BASE64_KEY = re.compile(r"^[A-Za-z0-9+/]{40,88}={0,2}$")


def classify(value):
    v = value.strip()
    if ETH_KEY.match(v):
        return {"kind": "eth_key", "tier": 2, "chain": "ethereum"}
    if SOL_KEY.match(v):
        return {"kind": "solana_key", "tier": 2, "chain": "solana"}
    if MNEMONIC_24.match(v):
        return {"kind": "mnemonic_24", "tier": 1, "chain": "multi"}
    if MNEMONIC_12.match(v):
        return {"kind": "mnemonic_12", "tier": 1, "chain": "multi"}
    if AWS_KEY.match(v):
        return {"kind": "aws_key", "tier": 3, "chain": "aws"}
    if OPENAI_KEY.match(v):
        return {"kind": "openai_key", "tier": 3, "chain": "openai"}
    if GH_TOKEN.match(v):
        return {"kind": "gh_token", "tier": 3, "chain": "github"}
    if SLACK_TOKEN.match(v):
        return {"kind": "slack_token", "tier": 3, "chain": "slack"}
    if BASE64_KEY.match(v):
        return {"kind": "base64_key", "tier": 3, "chain": "unknown"}
    if len(v) > 20:
        return {"kind": "generic_secret", "tier": 4, "chain": "unknown"}
    return {"kind": "unknown", "tier": 5, "chain": "unknown"}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 classify_secret.py <value>")
        sys.exit(1)

    value = sys.argv[1]
    result = classify(value)
    print(json.dumps(result, indent=2))


# Allow import without triggering main
import json

if __name__ == "__main__":
    main()
