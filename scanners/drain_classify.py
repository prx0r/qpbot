"""Drain authority classifier — what CAN this key do?

Not just "it's a private key" but:
  - Is it a root key (mnemonic) or derived?
  - Can it drain a wallet? Which chain?
  - Is it an API signing key (trade only) or a custodial key?
  - Is it a false positive (tx hash, contract address)?

Classification drives the prize pipeline: root keys get quarantined,
API keys get scoped, false positives get dropped.

Adapted from stallshark qp-wallet-drain-guard patterns.
"""
from __future__ import annotations

import json
import re
import sys

# ── Drain authority classes ───────────────────────────────────
# Ported from BLUE-TEAM-COMBINED.md drain-authority-audit.json

DERIVATION_ROOT = "DERIVATION_ROOT"          # BIP-39 mnemonic — master key
ROOT_SIGNER = "ROOT_SIGNER"                  # Raw private key — direct drain
SIGNING_DELEGATE = "SIGNING_DELEGATE"        # API signing key — trade only
CUSTODIAL_AUTHORITY = "CUSTODIAL_AUTHORITY"  # Exchange API secret — maybe
ENCRYPTED_CONTAINER = "ENCRYPTED_CONTAINER"  # Wallet keystore — depends
LOW_ENTRUSTMENT = "LOW_ENTRUSTMENT"          # Public address, test key, etc.
FALSE_POSITIVE = "FALSE_POSITIVE"            # Tx hash, contract address, etc.

# ── Detection patterns ───────────────────────────────────────

MNEMONIC_12 = re.compile(
    r"^([a-z]+\s+){11}[a-z]+$"
)
MNEMONIC_24 = re.compile(
    r"^([a-z]+\s+){23}[a-z]+$"
)
ETH_PRIVATE_KEY = re.compile(
    r"^(0x)?[0-9a-fA-F]{64}$"
)
SOL_PRIVATE_KEY = re.compile(
    r"^[1-9A-HJ-NP-Za-km-z]{64}$"
)
ETH_ADDRESS = re.compile(
    r"^(0x)?[0-9a-fA-F]{40}$"
)
BASE64_KEY = re.compile(
    r"^[A-Za-z0-9+/]{40,88}={0,2}$"
)
AWS_KEY = re.compile(r"^AKIA[0-9A-Z]{16}$")
OPENAI_KEY = re.compile(r"^sk-[A-Za-z0-9-]{20,}$")
GH_TOKEN = re.compile(r"^ghp_[A-Za-z0-9]{36}$")

# False positive indicators (context-based)
FP_INDICATORS = [
    "txhash", "blockhash", "input", "contractaddress",
    "from", "to", "hash", "nonce", "blocknumber",
    "tx_hash", "block_hash", "log_index",
]

REAL_INDICATORS = [
    "private_key", "secret_key", "signing_key",
    "mnemonic", "seed_phrase", ".env", "wallet",
    "keyfile", "keystore", "credentials",
]


def classify(value: str, context: str = "") -> dict:
    """Classify a secret value. Returns:
      class: drain authority class
      chain: eth/sol/multi/aws/other
      can_drain: bool
      confidence: 0.0-1.0
      reasoning: str
    """
    v = value.strip()
    ctx = context.lower()

    # ── False positive check (context-based) ──
    for ind in FP_INDICATORS:
        if ind in ctx:
            return {
                "class": FALSE_POSITIVE,
                "chain": "none",
                "can_drain": False,
                "confidence": 0.8,
                "reasoning": f"context contains '{ind}' — likely tx hash or calldata",
            }

    # ── Mnemonic (highest authority) ──
    if MNEMONIC_24.match(v):
        return {
            "class": DERIVATION_ROOT,
            "chain": "multi",
            "can_drain": True,
            "confidence": 0.95,
            "reasoning": "24-word BIP-39 mnemonic — can derive all chains",
        }
    if MNEMONIC_12.match(v):
        return {
            "class": DERIVATION_ROOT,
            "chain": "multi",
            "can_drain": True,
            "confidence": 0.9,
            "reasoning": "12-word BIP-39 mnemonic — can derive all chains",
        }

    # ── Raw private keys ──
    if ETH_PRIVATE_KEY.match(v):
        # Check if it's actually an address (40 hex vs 64 hex)
        stripped = v.replace("0x", "")
        if len(stripped) == 40:
            return {
                "class": LOW_ENTRUSTMENT,
                "chain": "eth",
                "can_drain": False,
                "confidence": 0.7,
                "reasoning": "40-char hex — likely an address, not a key",
            }
        for ind in REAL_INDICATORS:
            if ind in ctx:
                return {
                    "class": ROOT_SIGNER,
                    "chain": "eth",
                    "can_drain": True,
                    "confidence": 0.85,
                    "reasoning": f"64-char hex near '{ind}' — likely private key",
                }
        return {
            "class": ROOT_SIGNER,
            "chain": "eth",
            "can_drain": True,
            "confidence": 0.6,
            "reasoning": "64-char hex — could be private key or tx hash",
        }

    if SOL_PRIVATE_KEY.match(v):
        for ind in REAL_INDICATORS:
            if ind in ctx:
                return {
                    "class": ROOT_SIGNER,
                    "chain": "sol",
                    "can_drain": True,
                    "confidence": 0.85,
                    "reasoning": f"base58 64-char near '{ind}' — likely Solana key",
                }
        return {
            "class": ROOT_SIGNER,
            "chain": "sol",
            "can_drain": True,
            "confidence": 0.5,
            "reasoning": "base58 64-char — could be Solana key or random string",
        }

    # ── API keys (trade/delegate only) ──
    if AWS_KEY.match(v):
        return {
            "class": CUSTODIAL_AUTHORITY,
            "chain": "aws",
            "can_drain": False,
            "confidence": 0.9,
            "reasoning": "AWS access key — can access AWS services",
        }
    if OPENAI_KEY.match(v):
        return {
            "class": LOW_ENTRUSTMENT,
            "chain": "openai",
            "can_drain": False,
            "confidence": 0.9,
            "reasoning": "OpenAI API key — service access only",
        }
    if GH_TOKEN.match(v):
        return {
            "class": LOW_ENTRUSTMENT,
            "chain": "github",
            "can_drain": False,
            "confidence": 0.9,
            "reasoning": "GitHub PAT — repo access only",
        }

    # ── Base64 encoded keys ──
    if BASE64_KEY.match(v):
        for ind in REAL_INDICATORS:
            if ind in ctx:
                return {
                    "class": SIGNING_DELEGATE,
                    "chain": "unknown",
                    "can_drain": False,
                    "confidence": 0.6,
                    "reasoning": f"base64 key near '{ind}' — likely signing key",
                }
        return {
            "class": LOW_ENTRUSTMENT,
            "chain": "unknown",
            "can_drain": False,
            "confidence": 0.3,
            "reasoning": "base64 string — unclear purpose",
        }

    # ── Generic secret ──
    if len(v) > 20:
        return {
            "class": LOW_ENTRUSTMENT,
            "chain": "unknown",
            "can_drain": False,
            "confidence": 0.2,
            "reasoning": "long string — unknown type",
        }

    return {
        "class": FALSE_POSITIVE,
        "chain": "none",
        "can_drain": False,
        "confidence": 0.1,
        "reasoning": "short string — unlikely to be a key",
    }


def enrich(classification: dict, balance: dict | None = None) -> dict:
    """Add actionable metadata to a classification.

    This is the "what can this key DO" layer beyond "what IS this key".
    """
    c = dict(classification)
    c["actions"] = []

    if c["can_drain"]:
        if c["chain"] == "eth":
            c["actions"].append("drain_eth")
            c["actions"].append("drain_erc20")
            c["actions"].append("swap_to_xmr")
        elif c["chain"] == "sol":
            c["actions"].append("drain_sol")
            c["actions"].append("drain_spl")
            c["actions"].append("swap_to_xmr")
        elif c["chain"] == "multi":
            c["actions"].append("derive_eth")
            c["actions"].append("derive_sol")
            c["actions"].append("derive_btc")
            c["actions"].append("drain_all")

    if c["class"] == SIGNING_DELEGATE:
        c["actions"].append("trade_only")
        c["actions"].append("read_positions")

    if c["class"] == CUSTODIAL_AUTHORITY:
        c["actions"].append("possible_withdraw")
        c["actions"].append("read_balances")

    # Balance enrichment
    if balance:
        c["balance"] = balance
        total = balance.get("total_usd", 0)
        if total > 10000:
            c["priority"] = "critical"
        elif total > 1000:
            c["priority"] = "high"
        elif total > 0:
            c["priority"] = "medium"
        else:
            c["priority"] = "low"
    elif c["can_drain"]:
        c["priority"] = "check_balance"
    else:
        c["priority"] = "info"

    return c


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 drain_classify.py <value> [context]")
        sys.exit(1)

    value = sys.argv[1]
    context = sys.argv[2] if len(sys.argv) > 2 else ""
    result = classify(value, context)
    result = enrich(result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
