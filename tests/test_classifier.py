import tempfile, os

from agentcom.vault.classifier import classify, detect_wallets, tier_name
from agentcom.vault.scripts import run_scripts, check_password_strength, validate_mnemonic
from agentcom.vault.store import Vault


def test_classify_solana_key():
    # Real Solana key is 87-88 chars base58
    p = classify("66URqAQFPLzVBMnGxqYqEybTcKDqWvNkUMjBEjRMHmLgJYrVQBWHfpATnJKcS3QwSHJGpCBvBzQvJxBqYHkF3mj")
    assert p.kind == "solana_key"
    assert p.tier == 1
    assert p.chain == "solana"
    assert "check_sol_balance" in p.scripts


def test_classify_eth_key():
    p = classify("0x" + "a" * 64)
    assert p.kind == "eth_key"
    assert p.tier == 1
    assert p.chain == "eth"


def test_classify_aws_key():
    p = classify("AKIAIOSFODNN7EXAMPLE")
    assert p.kind == "aws_key"
    assert p.tier == 2
    assert p.chain == "aws"


def test_classify_github_token():
    p = classify("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij")
    assert p.kind == "github_token"
    assert p.tier == 2
    assert p.chain == "github"


def test_classify_openai_key():
    p = classify("sk-proj-abcdefghijklmnopqrstuvwx12")
    assert p.kind == "openai_key"
    assert p.tier == 2
    assert p.chain == "openai"


def test_classify_mnemonic():
    p = classify("MNEMONIC=abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about")
    assert p.kind == "mnemonic"
    assert p.tier == 3


def test_classify_generic():
    p = classify("some-random-api-key-1234567890abcdef")
    assert p.tier == 4


def test_detect_wallets():
    wallets = detect_wallets("address: 5cjcW9wExnJJiqgLjq7DEG75Pm6JBgE1hNv4B2vHXUW6 and 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18")
    sol = [w for w in wallets if w["chain"] == "solana"]
    eth = [w for w in wallets if w["chain"] == "eth"]
    assert len(sol) >= 1
    assert len(eth) >= 1


def test_scripts_sol_balance():
    r = run_scripts("66URqAQFPLzVBMnGxqYqEybTcKDqWvNkUMjBEjRMHmLgJYrVQBWHfpATnJKcS3QwSHJGpCBvBzQvJxBqYHkF3mj",
                    ["check_sol_balance", "derive_sol_address"])
    assert len(r) == 2
    assert all(s["ok"] for s in r)


def test_scripts_password_strength():
    r = check_password_strength("abc")
    assert r["score"] < 3
    r = check_password_strength("MyStr0ng!Passw0rd#2026")
    assert r["score"] >= 4


def test_scripts_mnemonic_validation():
    r = validate_mnemonic("MNEMONIC=abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about")
    assert r["valid_format"] is True
    assert r["word_count"] == 12


def test_capture_auto_classifies():
    d = tempfile.mkdtemp()
    v = Vault(os.path.join(d, "v.json"), os.path.join(d, "k"))
    p = v.capture("target-1", "agent-1", "abc", "rec-1",
                  found_secret="AKIAIOSFODNN7EXAMPLE",
                  found_name="captured-aws-01")
    assert p["key_type"] == "aws_key"
    assert p["key_tier"] == 2
    assert p["key_chain"] == "aws"
    assert "check_aws_identity" in p["scripts_run"]
    assert p["asset_stored"] is True
    # Stored with tier metadata
    s = v.secrets["captured-aws-01"]
    assert s["kind"] == "aws_key"
    assert s["tier"] == "tier-2"


def test_tier_name():
    assert tier_name(1) == "crypto-key"
    assert tier_name(2) == "cloud-api"
    assert tier_name(3) == "credential"
    assert tier_name(4) == "generic"
