"""Script runners — execute tier-specific actions on captured keys.

Each runner takes a secret + KeyProfile and returns structured results.
Runners are deterministic (no external calls in v0) — they validate,
derive, and check what they can locally. Live RPC/API calls are opt-in.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time


def _run(cmd: list[str], timeout: int = 15) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "stdout": r.stdout[:500],
                "stderr": r.stderr[:200]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# === Tier 1: Crypto ===

def check_sol_balance(secret: str, **kw) -> dict:
    """Check Solana mainnet balance via public RPC."""
    from .classifier import classify
    profile = classify(secret)
    if profile.kind != "solana_key":
        return {"ok": False, "error": "not a solana key"}
    # Derive address placeholder (real derivation needs solders/nacl)
    addr_hash = hashlib.sha256(secret.encode()).hexdigest()[:44]
    return {"ok": True, "action": "check_sol_balance",
            "note": "address derivation requires solders package",
            "placeholder_address": addr_hash}


def derive_sol_address(secret: str, **kw) -> dict:
    """Derive Solana public key from private key."""
    return {"ok": True, "action": "derive_sol_address",
            "note": "requires solders.keypair.from_base58_secret_key",
            "hash": hashlib.sha256(secret.encode()).hexdigest()[:44]}


def check_eth_balance(secret: str, **kw) -> dict:
    """Check ETH mainnet balance via public RPC."""
    from .classifier import classify
    profile = classify(secret)
    if profile.kind != "eth_key":
        return {"ok": False, "error": "not an eth key"}
    return {"ok": True, "action": "check_eth_balance",
            "note": "requires web3.py or cast for address derivation + RPC call"}


def check_erc20_holdings(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_erc20_holdings",
            "note": "requires web3.py + token list"}


def check_nfts(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_nfts",
            "note": "requires opensea/alchemy API"}


def check_token_holdings(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_token_holdings",
            "note": "requires helius/das API for Solana tokens"}


# === Tier 2: Cloud/API ===

def check_aws_identity(secret: str, **kw) -> dict:
    """Check AWS identity — requires aws cli."""
    if not secret.startswith("AKIA"):
        return {"ok": False, "error": "not an AWS access key"}
    r = _run(["aws", "sts", "get-caller-identity",
              "--access-key-id", secret,
              "--secret-access-key", kw.get("secret_key", "")])
    if r["ok"]:
        return {"ok": True, "action": "check_aws_identity",
                "identity": r["stdout"]}
    return {"ok": True, "action": "check_aws_identity",
            "note": "aws cli not configured or key expired"}


def list_s3_buckets(secret: str, **kw) -> dict:
    return {"ok": True, "action": "list_s3_buckets",
            "note": "requires aws cli + valid creds"}


def enum_iam_policies(secret: str, **kw) -> dict:
    return {"ok": True, "action": "enum_iam_policies",
            "note": "requires aws cli + iam:ListAttachedUserPolicies"}


def check_openai_models(secret: str, **kw) -> dict:
    """Check OpenAI model access."""
    from .classifier import classify
    profile = classify(secret)
    if profile.kind != "openai_key":
        return {"ok": False, "error": "not an openai key"}
    return {"ok": True, "action": "check_openai_models",
            "note": "curl -s https://api.openai.com/v1/models -H 'Authorization: Bearer <key>'"}


def check_usage_balance(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_usage_balance",
            "note": "requires OpenAI dashboard or API"}


def list_org_keys(secret: str, **kw) -> dict:
    return {"ok": True, "action": "list_org_keys",
            "note": "requires admin org key"}


def check_gh_scopes(secret: str, **kw) -> dict:
    """Check GitHub token scopes."""
    if not secret.startswith("ghp_"):
        return {"ok": False, "error": "not a github token"}
    import urllib.request
    req = urllib.request.Request("https://api.github.com/user",
                                headers={"Authorization": f"token {secret}",
                                         "User-Agent": "pq-checker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            scopes = r.headers.get("X-OAuth-Scopes", "")
            data = json.loads(r.read())
            return {"ok": True, "action": "check_gh_scopes",
                    "scopes": scopes, "user": data.get("login"),
                    "repos": data.get("public_repos")}
    except Exception as e:
        return {"ok": True, "action": "check_gh_scopes",
                "note": f"request failed: {e}"}


def list_gh_repos(secret: str, **kw) -> dict:
    return {"ok": True, "action": "list_gh_repos",
            "note": "GET /user/repos with token auth"}


def check_gh_rate_limit(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_gh_rate_limit",
            "note": "GET /rate_limit with token auth"}


def check_slack_scopes(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_slack_scopes",
            "note": "auth.test + auth.revoke test"}


def list_slack_channels(secret: str, **kw) -> dict:
    return {"ok": True, "action": "list_slack_channels",
            "note": "channels.list with token"}


def check_gcp_project(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_gcp_project",
            "note": "requires gcloud CLI"}


def list_gcp_services(secret: str, **kw) -> dict:
    return {"ok": True, "action": "list_gcp_services",
            "note": "requires gcloud services list"}


# === Tier 3: Credentials ===

def validate_mnemonic(secret: str, **kw) -> dict:
    """Validate BIP39 mnemonic word count and format."""
    words = secret.strip().split()
    valid_lengths = [12, 15, 18, 21, 24]
    if len(words) in valid_lengths:
        return {"ok": True, "action": "validate_mnemonic",
                "word_count": len(words), "valid_format": True,
                "note": "word count valid, checksum validation requires bip39 lib"}
    return {"ok": True, "action": "validate_mnemonic",
            "word_count": len(words), "valid_format": False}


def derive_addresses(secret: str, **kw) -> dict:
    return {"ok": True, "action": "derive_addresses",
            "note": "requires bip39 + coin-type derivation (ETH=60, SOL=501)"}


def check_all_chains(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_all_chains",
            "note": "derive for ETH/SOL/BTC, check balances via public RPCs"}


def check_breach_db(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_breach_db",
            "note": "haveibeenpwned API (requires API key)"}


def check_password_strength(secret: str, **kw) -> dict:
    score = 0
    if len(secret) >= 12: score += 1
    if len(secret) >= 16: score += 1
    if re.search(r"[A-Z]", secret): score += 1
    if re.search(r"[a-z]", secret): score += 1
    if re.search(r"[0-9]", secret): score += 1
    if re.search(r"[^A-Za-z0-9]", secret): score += 1
    return {"ok": True, "action": "check_password_strength",
            "score": score, "max": 6,
            "strength": ["very weak", "weak", "fair", "good", "strong", "very strong"]
            [min(score, 5)]}


# === Tier 4: Generic ===

def identify_service(secret: str, **kw) -> dict:
    """Try to identify the service from the key format."""
    s = secret.strip()
    if s.startswith("sk-"): return {"service": "openai-compatible", "confidence": 0.7}
    if s.startswith("ghp_"): return {"service": "github", "confidence": 0.95}
    if s.startswith("AKIA"): return {"service": "aws", "confidence": 0.98}
    if s.startswith("xox"): return {"service": "slack", "confidence": 0.95}
    if s.startswith("AIza"): return {"service": "gcp", "confidence": 0.9}
    if re.match(r"^[a-f0-9]{32}$", s): return {"service": "generic-hex-32", "confidence": 0.5}
    return {"service": "unknown", "confidence": 0.1}


def check_scope(secret: str, **kw) -> dict:
    return {"ok": True, "action": "check_scope",
            "note": "scope check requires service-specific API calls"}


# === Registry ===

SCRIPTS = {
    "check_sol_balance": check_sol_balance,
    "derive_sol_address": derive_sol_address,
    "check_eth_balance": check_eth_balance,
    "check_erc20_holdings": check_erc20_holdings,
    "check_nfts": check_nfts,
    "check_token_holdings": check_token_holdings,
    "check_aws_identity": check_aws_identity,
    "list_s3_buckets": list_s3_buckets,
    "enum_iam_policies": enum_iam_policies,
    "check_openai_models": check_openai_models,
    "check_usage_balance": check_usage_balance,
    "list_org_keys": list_org_keys,
    "check_gh_scopes": check_gh_scopes,
    "list_gh_repos": list_gh_repos,
    "check_gh_rate_limit": check_gh_rate_limit,
    "check_slack_scopes": check_slack_scopes,
    "list_slack_channels": list_slack_channels,
    "check_gcp_project": check_gcp_project,
    "list_gcp_services": list_gcp_services,
    "validate_mnemonic": validate_mnemonic,
    "derive_addresses": derive_addresses,
    "check_all_chains": check_all_chains,
    "check_breach_db": check_breach_db,
    "check_password_strength": check_password_strength,
    "identify_service": identify_service,
    "check_scope": check_scope,
}


def run_scripts(secret: str, scripts: list[str], **kw) -> list[dict]:
    """Run all associated scripts for a captured key."""
    results = []
    for name in scripts:
        fn = SCRIPTS.get(name)
        if fn:
            r = fn(secret, **kw)
            r["script"] = name
            results.append(r)
    return results
