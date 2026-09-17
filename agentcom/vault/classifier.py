"""Key classifier — detect secret type and assign tier + scripts.

Tier 1: Crypto private keys → balance, derive address, token holdings
Tier 2: Cloud/API keys → permissions, access level, service scope
Tier 3: Credentials (mnemonics, passwords) → breach check, reuse detection
Tier 4: Generic secrets → service identification, scope check
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class KeyProfile:
    kind: str  # solana_key, eth_key, mnemonic, api_key, aws_key, generic
    tier: int  # 1-4
    confidence: float  # 0.0-1.0
    chain: str  # solana, eth, aws, openai, etc.
    scripts: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


PATTERNS = [
    # Tier 1: Crypto private keys
    {"pattern": r"^[1-9A-HJ-NP-Za-km-z]{87,88}$", "kind": "solana_key",
     "tier": 1, "chain": "solana", "confidence": 0.95,
     "scripts": ["check_sol_balance", "derive_sol_address", "check_token_holdings"]},
    {"pattern": r"^(0x)?[0-9a-fA-F]{64}$", "kind": "eth_key",
     "tier": 1, "chain": "eth", "confidence": 0.9,
     "scripts": ["check_eth_balance", "check_erc20_holdings", "check_nfts"]},
    {"pattern": r"(?:MNEMONIC|SEED|RECOVERY|PHRASE)[\s:=]+(.+)",
     "kind": "mnemonic", "tier": 3, "chain": "multi", "confidence": 0.85,
     "scripts": ["validate_mnemonic", "derive_addresses", "check_all_chains"]},

    # Tier 2: Cloud/API keys
    {"pattern": r"^(AKIA[0-9A-Z]{16})$", "kind": "aws_key",
     "tier": 2, "chain": "aws", "confidence": 0.98,
     "scripts": ["check_aws_identity", "list_s3_buckets", "enum_iam_policies"]},
    {"pattern": r"^sk-[a-zA-Z0-9][a-zA-Z0-9-]{18,}$", "kind": "openai_key",
     "tier": 2, "chain": "openai", "confidence": 0.9,
     "scripts": ["check_openai_models", "check_usage_balance", "list_org_keys"]},
    {"pattern": r"^ghp_[a-zA-Z0-9]{36}$", "kind": "github_token",
     "tier": 2, "chain": "github", "confidence": 0.95,
     "scripts": ["check_gh_scopes", "list_gh_repos", "check_gh_rate_limit"]},
    {"pattern": r"^xox[bpsa]-[a-zA-Z0-9-]+$", "kind": "slack_token",
     "tier": 2, "chain": "slack", "confidence": 0.95,
     "scripts": ["check_slack_scopes", "list_slack_channels"]},
    {"pattern": r"^AIza[0-9A-Za-z_-]{35}$", "kind": "gcp_key",
     "tier": 2, "chain": "gcp", "confidence": 0.9,
     "scripts": ["check_gcp_project", "list_gcp_services"]},

    # Tier 3: Credentials
    {"pattern": r"(?:PASSWORD|PASSWD|PWD)[\s:=]+(.+)",
     "kind": "password", "tier": 3, "chain": "none", "confidence": 0.8,
     "scripts": ["check_breach_db", "check_password_strength"]},

    # Tier 4: Generic
    {"pattern": r"(?:API_KEY|SECRET_KEY|ACCESS_KEY|TOKEN)[\s:=]+(.+)",
     "kind": "generic_secret", "tier": 4, "chain": "unknown", "confidence": 0.6,
     "scripts": ["identify_service", "check_scope"]},
]

# Wallet address patterns (not secrets, but useful for context)
WALLET_PATTERNS = [
    {"pattern": r"\b0x[0-9a-fA-F]{40}\b", "chain": "eth", "kind": "eth_wallet"},
    {"pattern": r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b", "chain": "solana", "kind": "sol_wallet"},
]


def classify(secret: str) -> KeyProfile:
    """Detect key type from a secret string. Returns KeyProfile with tier
    and associated scripts."""
    s = secret.strip()
    for p in PATTERNS:
        m = re.search(p["pattern"], s, re.IGNORECASE)
        if m:
            return KeyProfile(
                kind=p["kind"], tier=p["tier"], confidence=p["confidence"],
                chain=p["chain"], scripts=list(p["scripts"]),
                metadata={"matched": p["pattern"][:40]})
    # Fallback: high-entropy string = generic secret
    if len(s) >= 16 and len(set(s)) > 10:
        return KeyProfile(kind="generic_secret", tier=4, confidence=0.4,
                          chain="unknown", scripts=["identify_service"])
    return KeyProfile(kind="unknown", tier=4, confidence=0.0,
                      chain="unknown", scripts=[])


def detect_wallets(text: str) -> list[dict]:
    """Extract wallet addresses from text (for context, not as secrets)."""
    wallets = []
    for p in WALLET_PATTERNS:
        for m in re.finditer(p["pattern"], text):
            wallets.append({"address": m.group(0), "chain": p["chain"],
                            "kind": p["kind"]})
    return wallets


def tier_name(tier: int) -> str:
    return {1: "crypto-key", 2: "cloud-api", 3: "credential", 4: "generic"
            }.get(tier, "unknown")
